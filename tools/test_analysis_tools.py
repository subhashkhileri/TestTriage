import io
import xml.etree.ElementTree as ET
from typing import List
from langchain_core.tools import tool
from PIL import Image
import google.generativeai as genai
from jira import JIRA
import os
from utils.storage import storage_client
from config.settings import settings

@tool
def get_failed_testsuites(xml_file_prefix: str):
    """
    Get test suites from junit xml with failures.
    
    Args:
        xml_file_prefix (str): Path to XML file
        
    Returns:
        str: XML string of failed testsuites
    """
    try:
        root = ET.fromstring(storage_client.get_text_from_blob(xml_file_prefix))
        testsuites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
        failed_testsuites = []
        for testsuite in testsuites:
            failures = int(testsuite.get('failures', '0'))
            if failures > 0:
                for element in testsuite.iter():
                    system_outs = element.findall('system-out')
                    for system_out in system_outs:
                        element.remove(system_out)
                failed_testsuites.append(ET.tostring(testsuite, encoding='unicode'))
        return '\n'.join(failed_testsuites)
    except Exception as e:
        return f"Error getting failed testsuites: {e}"

@tool
def analyze_screenshot_visual_confirmation(image_path: str, test_failure_analysis_text: str, test_title: str, junit_xml_failure: str):
    """Analyze a screenshot image along with provided test failure analysis text to give a visual confirmation or insights from the image.
    Args:
        image_path (str): The file path to the screenshot image.
        test_failure_analysis_text (str): The test failure analysis text.
        test_title (str): The title of the test.
        junit_xml_failure (str): full Test failure/Error from the <failure> tag in the JUnit XML.
    Returns:
        str: The root cause analysis and screenshot analysis.
    """
    try:
        model = genai.GenerativeModel(settings.GEMINI_MODEL_NAME) 
        
        try:
            image_data = storage_client.get_bytes_from_blob(image_path)
            image_stream = io.BytesIO(image_data)
            image = Image.open(image_stream)
        except Exception as e:
            image = None
        
        prompt_with_image = f"""
**Objective:** Provide a BRIEF visual analysis of the test failure screenshot with emphasis on visual evidence.

**Test Context:**
- Test Name: {test_title}
- Test Failure Analysis: {test_failure_analysis_text}
- JUnit XML Failure: {junit_xml_failure}

**Required Brief Analysis (Keep concise - 3-4 sentences per section):**

## 🔍 VISUAL EVIDENCE
**What the screenshot shows:**
- Key UI elements visible (buttons, forms, error messages, states)
- Visual anomalies or unexpected elements
- Current application state/page

## 🔗 VISUAL-TO-FAILURE CORRELATION
**How visuals connect to test failure:**
- Expected vs actual visual state
- Which test step this screenshot represents
- Visual indicators of the failure point

## 🎯 VISUAL ROOT CAUSE
**Primary cause based on visual evidence:**
- Main issue visible in screenshot
- Visual confirmation of technical failure
- Actionable fix based on what's seen

**Requirements:**
- Prioritize visual observations over technical speculation
- Keep each section to 2-3 concise bullet points
- Focus on what can be directly observed in the image
- Emphasize visual evidence throughout
"""

        prompt_without_image = f"""
**Objective:** Provide a BRIEF analysis of test failure context when no visual evidence is available.

**Test Context:**
- Test Name: {test_title}
- Test Failure Analysis: {test_failure_analysis_text}
- JUnit XML Failure: {junit_xml_failure}

**Required Analysis Structure:**

## 1. TEST CONTEXT ANALYSIS
Examine the available test information:
- Test purpose and expected behavior
- Failure message interpretation
- Error patterns and stack traces
- Test execution environment indicators

## 2. FAILURE PATTERN IDENTIFICATION
Identify the type and nature of the failure:
- **Error Category:** (UI, API, timing, configuration, etc.)
- **Failure Timing:** When in the test execution the failure occurred
- **Error Propagation:** How the error manifested through the system
- **Impact Scope:** What parts of the application are affected

## 3. ROOT CAUSE DETERMINATION
Based on available context:
- **Primary Cause:** The main reason for failure based on error analysis
- **Contributing Factors:** Additional issues indicated by the failure data
- **Test Validity:** Whether the failure indicates app issues or test problems
- **Actionable Insights:** Specific steps to resolve based on error analysis

**Note:** Screenshot analysis would provide additional visual context for more comprehensive root cause analysis.

**Requirements:**
- Keep analysis under 100 words total
- Focus on actionable insights
- Prioritize error message interpretation
"""
        response = model.generate_content([prompt_with_image, image] if image else prompt_without_image)
        return response.text
    except Exception as e:
        return f"Error during screenshot analysis: {str(e)}"

@tool
def get_text_from_file(file_path: str):
    """Get the text from a file from the given file path and return the text.
    Args:
        file_path (str): The path of the file to get the text from.
    Returns:
        str: The text of the file.
    """
    return storage_client.get_text_from_blob(file_path)

@tool
def get_folder_structure(prefix: str):
    """Get the tree/folder structure output from the given prefix and return the tree output.
    Args:
        prefix (str): The prefix of the folder to get the structure of.
    Returns:
        str: The tree/folder structure output.
    """
    print("get_folder_structure:" + prefix)
    try:
        blob_names = storage_client.list_blobs(prefix)
        rel_paths = []
        for path in blob_names:
            rel_path = path[len(prefix):].strip('/')
            if rel_path:
                rel_paths.append(rel_path)
        
        rel_paths.sort()
        
        seen_dirs = set()
        tree_output = []
        for path in rel_paths:
            parts = path.split('/')
            for level, part in enumerate(parts):
                current_path = '/'.join(parts[:level+1])
                if current_path not in seen_dirs:
                    seen_dirs.add(current_path)
                    indent = "  " * level  # 2 spaces per level
                    if level == len(parts) - 1:
                        tree_output.append(f"{indent}{part}")
                    else:
                        tree_output.append(f"{indent}{part}/")
        return '\n'.join(tree_output)
    except Exception as e:
        return f"Error getting folder structure: {e}"

@tool
def get_texts_from_files(file_paths: List[str]):
    """Get the text from a list of files from the given file paths and return the text.
    Args:
        file_paths (List[str]): The list of file paths to get the text of.
    Returns:
        List[str]: The list of text of the files.
    """
    try:
        contents = []
        for file_path in file_paths:
            try:
                contents.append(storage_client.get_text_from_blob(file_path))
            except Exception as e:
                contents.append(f"Error reading file {file_path}: {e}")
        return contents
    except Exception as e:
        return f"Error getting texts from files: {e}"

@tool
def get_immediate_log_files_content(prefix: str):
    """Get the concatenated content of all immediate .log files from the given prefix.
    Args:
        prefix (str): The prefix path to search for immediate .log files.
    Returns:
        str: The concatenated content of all .log files with file names as headers.
    """
    try:
        # Get all immediate files from the prefix
        immediate_files = storage_client.get_immediate_files(prefix)
        
        # Filter for .log files
        log_files = [f for f in immediate_files if f.endswith('.log')]
        
        if not log_files:
            return f"No .log files found in the immediate directory of prefix: {prefix}"
        
        concatenated_content = []
        
        for log_file in log_files:
            # Construct full path
            full_path = f"{prefix.rstrip('/')}/{log_file}"
            
            try:
                # Get content of the log file
                content = storage_client.get_text_from_blob(full_path)
                
                # Add file header and content
                concatenated_content.append(f"=== {log_file} ===")
                concatenated_content.append(content)
                concatenated_content.append("")  # Empty line for separation
                
            except Exception as e:
                concatenated_content.append(f"=== {log_file} ===")
                concatenated_content.append(f"Error reading file {log_file}: {e}")
                concatenated_content.append("")
        
        return '\n'.join(concatenated_content)
        
    except Exception as e:
        return f"Error getting immediate log files content: {e}"

@tool
def create_jira_bug(
    summary: str,
    description: str,
    image_path: str = None,
    prowlink: str = None
):
    """
    Create a Jira bug ticket only when user asks to create a Jira bug.
    
    Args:
        summary (str): JIRA ticket summary/title.
        description (str): Detailed description of the bug including Test purpose, failure message, root cause analysis and screenshot analysis, etc.
        image_path (str): GCS Path to screenshot file to attach to the ticket from JUnit XML failure.
        prowlink (str): Prow link to the test failure log.
        
    Returns:
        str: Success message with ticket key and url or error message
    """
    try:
        jira_client = JIRA(
            server="https://issues.redhat.com/",
            token_auth=os.getenv("JIRA_PAT")
        )
        
        issue_dict = {
            'project': {'key': 'RHIDP'},
            'summary': summary,
            'description': description,
            'issuetype': {'name': 'Bug'},
            'labels': ['ci-fail']
        }
        
        new_issue = jira_client.create_issue(fields=issue_dict)

        # Attach image if provided
        attachment_info = ""
        if image_path is not None:
            try:
                # Get image data from storage
                image_data = storage_client.get_bytes_from_blob(image_path)
                
                # Extract filename from path
                filename = image_path.split('/')[-1]
                if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    filename += '.png'  # Default to PNG if no extension
                
                # Create a file-like object from bytes
                image_stream = io.BytesIO(image_data)
                
                # Attach the image to the issue
                jira_client.add_attachment(issue=new_issue, attachment=image_stream, filename=filename)
                attachment_info = f"\nImage attached: {filename}"
                
            except Exception as attach_error:
                attachment_info = f"\nWarning: Failed to attach image - {str(attach_error)}"

        # Add prowlink as remote link if provided
        link_info = ""
        if prowlink is not None:
            try:
                # Add the prow link as a remote link
                jira_client.add_remote_link(
                    issue=new_issue,
                    destination={
                        'url': prowlink,
                        'title': 'Prow Test Failure Log'
                    }
                )
                link_info = f"\nProw link attached: {prowlink}"
                
            except Exception as link_error:
                link_info = f"\nWarning: Failed to attach prow link - {str(link_error)}"
        
        ticket_url = f"https://issues.redhat.com/browse/{new_issue.key}"
        
        return f"Jira bug created successfully!\nTicket Key: {new_issue.key}{attachment_info}{link_info}\nURL: {ticket_url}"
        
    except Exception as e:
        error_msg = str(e)
        
        if "401" in error_msg or "Unauthorized" in error_msg:
            return f"Authentication failed. Please check your JIRA_PAT environment variable: {error_msg}"
        elif "403" in error_msg or "Forbidden" in error_msg:
            return f"Permission denied. Check if you have permission to create issues in project 'RHIDP': {error_msg}"
        elif "404" in error_msg or "Not Found" in error_msg:
            return f"Project 'RHIDP' not found or Jira URL is incorrect: {error_msg}"
        else:
            return f"Error creating Jira bug: {error_msg}"

@tool
def update_jira_bug(
    ticket_key: str,
    summary: str = None,
    description: str = None,
    image_path: str = None,
    prowlink: str = None
):
    """
    Update an existing Jira bug ticket.
    
    Args:
        ticket_key (str): Jira ticket key (e.g., RHIDP-1234)
        summary (str, optional): New summary for the bug
        description (str, optional): New description for the bug
        image_path (str): GCS Path to screenshot file to attach to the ticket from JUnit XML failure.
        prowlink (str): Prow link to the test failure log.
            
    Returns:
        str: Success message with ticket key and url or error message
    """
    try:
        jira_client = JIRA(
            server="https://issues.redhat.com/",
            token_auth=os.getenv("JIRA_PAT")
        )
        
        # Get the issue to verify it exists
        issue = jira_client.issue(ticket_key)
        
        # Prepare fields to update
        update_fields = {}
        if summary is not None:
            update_fields['summary'] = summary
        if description is not None:
            update_fields['description'] = description
            
        # Update the issue if there are fields to update
        if update_fields:
            issue.update(fields=update_fields)

        # Attach image if provided
        attachment_info = ""
        if image_path is not None:
            try:
                # Get image data from storage
                image_data = storage_client.get_bytes_from_blob(image_path)
                
                # Extract filename from path
                filename = image_path.split('/')[-1]
                if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    filename += '.png'  # Default to PNG if no extension
                
                # Create a file-like object from bytes
                image_stream = io.BytesIO(image_data)
                
                # Attach the image to the issue
                jira_client.add_attachment(issue=issue, attachment=image_stream, filename=filename)
                attachment_info = f"\nImage attached: {filename}"
                
            except Exception as attach_error:
                attachment_info = f"\nWarning: Failed to attach image - {str(attach_error)}"

        # Add prowlink as remote link if provided
        link_info = ""
        if prowlink is not None:
            try:
                # Add the prow link as a remote link
                jira_client.add_remote_link(
                    issue=issue,
                    destination={
                        'url': prowlink,
                        'title': 'Prow Test Failure Log'
                    }
                )
                link_info = f"\nProw link attached: {prowlink}"
                
            except Exception as link_error:
                link_info = f"\nWarning: Failed to attach prow link - {str(link_error)}"

        ticket_url = f"https://issues.redhat.com/browse/{ticket_key}"
        
        updated_fields = []
        if summary is not None:
            updated_fields.append("summary")
        if description is not None:
            updated_fields.append("description")
            
        fields_str = ", ".join(updated_fields) if updated_fields else "no fields"
        
        return f"Jira bug updated successfully!\nTicket Key: {ticket_key}\nUpdated fields: {fields_str}{attachment_info}{link_info}\nURL: {ticket_url}"
        
    except Exception as e:
        error_msg = str(e)
        
        if "401" in error_msg or "Unauthorized" in error_msg:
            return f"Authentication failed. Please check your JIRA_PAT environment variable: {error_msg}"
        elif "403" in error_msg or "Forbidden" in error_msg:
            return f"Permission denied. Check if you have permission to update issue '{ticket_key}': {error_msg}"
        elif "404" in error_msg or "Not Found" in error_msg:
            return f"Issue '{ticket_key}' not found or Jira URL is incorrect: {error_msg}"
        else:
            return f"Error updating Jira bug: {error_msg}"

@tool
def search_jira_bugs(
    jql_query: str
):
    """
    Search for existing Jira bugs using a custom JQL query based on detailed description of the failure including Test purpose, failure message from JUnit XML, root cause analysis and screenshot analysis, etc.  no component, label, just use summary and text
    
    Args:
        jql_query (str): JQL query to search for issues based on detailed description of the failure including Test purpose, failure message from JUnit XML, root cause analysis and screenshot analysis, etc.  no component, label, just use summary and text
        
    Returns:
        str: List of matching issues with key, summary, status, and URL or error message
    """
    try:
        jira_client = JIRA(
            server="https://issues.redhat.com/",
            token_auth=os.getenv("JIRA_PAT")
        )
        
        # Ensure the query includes project restriction to RHIDP
        if "project" not in jql_query.lower():
            # Add project constraint if not already present
            final_jql_query = f"project = RHIDP AND ({jql_query})"
        else:
            # Use the query as-is if it already includes project specification
            final_jql_query = jql_query
        
        # Search for issues using the modified JQL query
        issues = jira_client.search_issues(final_jql_query, maxResults=3)
        
        if not issues:
            return f"No matching issues found for JQL query: '{final_jql_query}'"
        
        # Format results
        results = []
        results.append(f"Found {len(issues)} matching issue(s) for query: '{final_jql_query}':")
        results.append("")
        
        for issue in issues:
            # Get basic issue info
            key = issue.key
            status = issue.fields.status.name
            issue_type = issue.fields.issuetype.name
            
            # Build issue URL
            issue_url = f"https://issues.redhat.com/browse/{key}"
            
            # Format each issue
            issue_info = f"""
Type: {issue_type}
Status: {status}
URL: {issue_url}
---"""
            results.append(issue_info)
        
        return '\n'.join(results)
        
    except Exception as e:
        error_msg = str(e)
        
        if "401" in error_msg or "Unauthorized" in error_msg:
            return f"Authentication failed. Please check your JIRA_PAT environment variable: {error_msg}"
        elif "403" in error_msg or "Forbidden" in error_msg:
            return f"Permission denied. Check if you have permission to search Jira: {error_msg}"
        elif "400" in error_msg or "Bad Request" in error_msg:
            return f"Invalid JQL query. Please check your JQL syntax: {error_msg}"
        else:
            return f"Error searching Jira bugs: {error_msg}"

# List of all available tools
TOOLS = [
    get_text_from_file,
    get_failed_testsuites,
    analyze_screenshot_visual_confirmation,
    get_immediate_log_files_content,
    create_jira_bug,
    search_jira_bugs,
] 