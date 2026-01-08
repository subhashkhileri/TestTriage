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

# Add these imports at the top of test_analysis_tools.py
import chromadb
from chromadb.config import Settings
import json

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
**Objective:** Analyze the screenshot and provide a comprehensive Root Cause Analysis that will be used directly in a markdown report.

**Test Context:**
- Test Name: {test_title}
- Test Failure Analysis: {test_failure_analysis_text}
- JUnit XML Failure: {junit_xml_failure}

**CRITICAL: Return your analysis in EXACTLY this format (this will be inserted directly into the report):**

[2-3 comprehensive sentences that combine the root cause statement with visual evidence. First sentence should identify the root cause clearly (e.g., "The root cause is..."). Following sentences should describe what the screenshot shows and how it correlates to the failure, providing technical details about UI elements, states, and context.]

**Example Format:**
"The root cause is that the test is using an incorrect or outdated data-testid selector to locate the 'Overview' tab, leading to a timeout even though the element is visually present. The screenshot shows the Red Hat Developer Hub application displaying a user's profile page, where the 'Overview' tab is clearly visible and selected as the active tab in the main content area."

**Requirements:**
- Write 2-3 comprehensive sentences as a single flowing paragraph
- First sentence MUST start with "The root cause is..." and identify the specific technical issue
- Following sentences should describe observable facts from the screenshot (UI state, visible elements, error messages, page state, anomalies)
- Be specific about UI elements, their states, positions, and any visible context
- Explain the correlation between what's visible and why the test failed
- Use complete sentences in paragraph form, not bullet points or separate sections
- Do NOT use markdown headers (##), bold text (**), or emojis in your response
- Do NOT include section labels like "Visual Evidence:" or "Conclusion:"
"""

        prompt_without_image = f"""
**Objective:** Analyze the test failure and provide a comprehensive Root Cause Analysis when no screenshot is available.

**Test Context:**
- Test Name: {test_title}
- Test Failure Analysis: {test_failure_analysis_text}
- JUnit XML Failure: {junit_xml_failure}

**CRITICAL: Return your analysis in EXACTLY this format (this will be inserted directly into the report):**

[2-3 comprehensive sentences that combine the root cause statement with error analysis. First sentence should identify the root cause clearly (e.g., "The root cause is..."). Following sentences should analyze the error message, stack trace, and test context to explain what likely happened during test execution and why the failure occurred.]

**Requirements:**
- Write 2-3 comprehensive sentences as a single flowing paragraph
- First sentence MUST start with "The root cause is..." and identify the specific technical issue
- Following sentences should analyze the error message, stack trace patterns, timing issues, element state issues, or other technical factors
- Be specific and technical in explaining the chain of events or conditions that led to the failure
- Explain what the test was attempting to do and why it failed based on the error evidence
- Use complete sentences in paragraph form, not bullet points or separate sections
- Do NOT use markdown headers (##), bold text (**), or emojis in your response
- Do NOT include section labels like "Visual Evidence:" or "Conclusion:"
- Focus on error message interpretation and test context analysis
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
def get_immediate_directories(prefix: str):
    """Get immediate subdirectory names from a given prefix path (only first level, not recursive).
    Args:
        prefix (str): The prefix path to search for immediate subdirectories.
    Returns:
        str: Comma-separated list of immediate directory names or error message.
    """
    try:
        directories = storage_client.get_immediate_directories(prefix)
        if not directories:
            return f"No immediate subdirectories found at prefix: {prefix}"
        return ", ".join(directories)
    except Exception as e:
        return f"Error getting immediate directories: {e}"

@tool
def get_immediate_files(prefix: str):
    """Get immediate file names from a given prefix path (only first level, not in subdirectories).
    Args:
        prefix (str): The prefix path to search for immediate files.
    Returns:
        str: Comma-separated list of immediate file names or error message.
    """
    try:
        files = storage_client.get_immediate_files(prefix)
        if not files:
            return f"No immediate files found at prefix: {prefix}"
        return ", ".join(files)
    except Exception as e:
        return f"Error getting immediate files: {e}"

@tool
def check_file_exists(file_path: str):
    """Check if a file exists at the given path.
    Args:
        file_path (str): The file path to check.
    Returns:
        str: "exists" or "not found"
    """
    try:
        exists = storage_client.blob_exists(file_path)
        return "exists" if exists else "not found"
    except Exception as e:
        return f"Error checking file existence: {e}"

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
        summary (str): JIRA ticket summary/title (max 255 chars, will be truncated if longer).
        description (str): Detailed description of the bug including Test purpose, failure message, root cause analysis and screenshot analysis, etc.
        image_path (str): GCS Path to screenshot file to attach to the ticket from JUnit XML failure.
        prowlink (str): Prow link to the test failure log.

    Returns:
        str: Success message with ticket key and url or error message
    """
    try:
        # Check for JIRA_PAT first
        jira_pat = os.getenv("JIRA_PAT")
        if not jira_pat:
            return "Error: JIRA_PAT environment variable is not set. Please configure your Jira Personal Access Token."

        # Input validation
        if not summary or not summary.strip():
            return "Error: Summary cannot be empty"

        if not description or not description.strip():
            return "Error: Description cannot be empty"

        # Truncate summary to Jira's 255 character limit
        max_summary_length = 255
        original_summary = summary
        if len(summary) > max_summary_length:
            summary = summary[:max_summary_length - 3] + "..."
            truncation_note = f"\n(Note: Summary was truncated from {len(original_summary)} to {max_summary_length} characters)"
        else:
            truncation_note = ""

        jira_client = JIRA(
            server="https://issues.redhat.com/",
            token_auth=jira_pat
        )

        # RHDHBUGS requires summary field on creation
        # Build the initial issue dict with required fields
        issue_dict = {
            'project': {'key': 'RHDHBUGS'},
            'issuetype': {'name': 'Bug'},
            'summary': summary.strip(),
            'versions': [{'name': '1.9.0'}]  # Affects Version/s - required field
        }

        # Add description if provided
        if description and description.strip():
            issue_dict['description'] = description.strip()

        print(f"Creating JIRA issue in RHDHBUGS project...")
        new_issue = jira_client.create_issue(fields=issue_dict)
        print(f"✓ Issue created: {new_issue.key}")

        # Track any errors that occur during optional updates
        update_errors = []

        # Try to add labels separately (this is optional)
        try:
            print(f"Adding label 'ci-fail' to issue {new_issue.key}...")
            new_issue.update(fields={'labels': ['ci-fail']})
            print(f"✓ Successfully added label")
        except Exception as e:
            error_msg = str(e)
            update_errors.append(f"Could not add labels: {error_msg}")
            print(f"⚠ Warning: {update_errors[-1]}")

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

        # Build warning message if there were any update errors
        warnings = ""
        if update_errors:
            warnings = "\n\nWarnings:\n" + "\n".join(f"  - {err}" for err in update_errors)

        return f"Jira bug created successfully!\nTicket Key: {new_issue.key}{truncation_note}{attachment_info}{link_info}\nURL: {ticket_url}{warnings}"

    except Exception as e:
        error_msg = str(e)

        # Enhanced error handling for specific cases
        if "401" in error_msg or "Unauthorized" in error_msg:
            return f"Authentication failed. Please check your JIRA_PAT environment variable: {error_msg}"
        elif "403" in error_msg or "Forbidden" in error_msg:
            return f"Permission denied. Check if you have permission to create issues in project 'RHDHBUGS': {error_msg}"
        elif "404" in error_msg or "Not Found" in error_msg:
            return f"Project 'RHDHBUGS' not found or Jira URL is incorrect: {error_msg}"
        elif "400" in error_msg:
            # Parse HTTP 400 errors for field validation issues
            if "Field" in error_msg and "cannot be set" in error_msg:
                return (f"Field validation error. The RHDHBUGS project may have custom required fields or screen configurations.\n"
                       f"Error details: {error_msg}\n"
                       f"Suggestion: Check the project's create issue screen configuration in Jira.")
            elif "component" in error_msg.lower():
                return f"Component error. The specified component may not exist in RHDHBUGS project: {error_msg}"
            elif "priority" in error_msg.lower():
                return f"Priority error. The specified priority may not be valid: {error_msg}"
            else:
                return f"Bad request (HTTP 400). Check input values: {error_msg}"
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


# Initialize ChromaDB client and embedding model (add after imports, before tools)
_chroma_client = None
_embedding_model_name = None
_jira_collection = None

def _get_chroma_resources():
    """Lazy initialization of ChromaDB and embedding model."""
    global _chroma_client, _embedding_model_name, _jira_collection

    if _chroma_client is None:
        chroma_persist_dir = os.getenv("CHROMA_PERSIST_DIR", settings.chroma_db_dir)
        _chroma_client = chromadb.PersistentClient(
            path=chroma_persist_dir,
            settings=Settings(anonymized_telemetry=False)
        )

    if _embedding_model_name is None:
        # Initialize Google API if not already configured
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if google_api_key:
            genai.configure(api_key=google_api_key)
        _embedding_model_name = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")

    if _jira_collection is None:
        _jira_collection = _chroma_client.get_or_create_collection(
            name="jira_issues",
            metadata={"description": "RHDHBUGS Jira issues for semantic similarity search"}
        )

    return _chroma_client, _embedding_model_name, _jira_collection


@tool
def search_similar_jira_issues(
    failure_description: str,
    test_name: str = None,
    error_message: str = None,
    top_k: int = 2,
    similarity_threshold: float = 0.45
):
    """
    Search for similar Jira issues using semantic similarity based on test failure information.
    This tool uses AI embeddings to find historically reported issues that are semantically similar
    to the current failure, even if they use different wording.

    Args:
        failure_description (str): Comprehensive description of the test failure including root cause analysis,
                                  visual evidence from screenshots, and failure context. This should be the
                                  complete analysis generated by the agent.
        test_name (str, optional): Name of the failed test to improve matching accuracy.
        error_message (str, optional): Error message from JUnit XML to improve matching accuracy.
        top_k (int): Number of similar issues to return (default: 2, max: 2). Returns max 2 most relevant issues.
        similarity_threshold (float): Minimum similarity score (0-1) to include results (default: 0.45).
                                     Lower threshold to catch more semantically related issues.

    Returns:
        str: Formatted list of up to 2 most similar issues, prioritizing open issues.
             Returns message if no similar issues found above threshold.
    """
    try:
        # Get ChromaDB resources
        _, embedding_model_name, collection = _get_chroma_resources()

        # Check if collection has any data
        if collection.count() == 0:
            return ("No Jira issues found in the database. Please run jira_sync_to_chroma.py "
                   "to populate the database with existing issues.")

        # Validate top_k - max 2 results
        top_k = min(max(1, top_k), 2)  # Clamp between 1 and 2

        # Validate similarity_threshold
        similarity_threshold = max(0.0, min(1.0, similarity_threshold))

        # Construct comprehensive search query - prioritize error message for better matching
        search_components = []

        # Put error message first as it's most specific for matching
        if error_message:
            search_components.append(f"Error Message: {error_message}")

        # Add failure description
        search_components.append(f"Failure Description: {failure_description}")

        if test_name:
            search_components.append(f"Test Name: {test_name}")

        search_query = "\n".join(search_components)

        # Generate embedding for the search query using Google's API
        result = genai.embed_content(
            model=embedding_model_name,
            content=search_query,
            task_type="retrieval_query"
        )
        query_embedding = result['embedding']

        # Search for similar issues - fetch more than needed to allow for filtering and prioritization
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=10  # Fetch more to allow prioritizing open issues
        )
        
        # Process results
        if not results['ids'] or not results['ids'][0]:
            return "No similar issues found in the database."
        
        # Extract results
        ids = results['ids'][0]
        distances = results['distances'][0]
        metadatas = results['metadatas'][0]
        documents = results['documents'][0]
        
        # Convert distances to similarity scores (cosine similarity)
        # ChromaDB returns L2 distances, convert to similarity
        similarities = [1 - (dist / 2) for dist in distances]
        
        # Filter by threshold
        filtered_results = []
        for i, similarity in enumerate(similarities):
            if similarity >= similarity_threshold:
                status = metadatas[i].get('status', '').lower()
                # Determine if issue is open (not closed/resolved/done)
                is_open = status not in ['closed', 'resolved', 'done']
                filtered_results.append({
                    'key': ids[i],
                    'similarity': similarity,
                    'metadata': metadatas[i],
                    'document': documents[i],
                    'is_open': is_open
                })

        if not filtered_results:
            # Show the best match even if below threshold for debugging
            if similarities:
                best_idx = similarities.index(max(similarities))
                best_similarity = similarities[best_idx] * 100
                best_key = metadatas[best_idx].get('key', 'N/A')
                best_summary = metadatas[best_idx].get('summary', 'N/A')[:80]
                return (f"No similar issues found with similarity >= {similarity_threshold*100:.0f}%. "
                       f"Closest match: {best_key} ({best_similarity:.1f}%) - \"{best_summary}...\"")
            return "No similar issues found in the database."

        # Sort by weighted score: similarity + 10% boost for open issues
        # This prioritizes open issues while still respecting relevance
        # e.g., 80% closed vs 75% open -> 80% vs 85% (weighted) -> open wins
        # but 90% closed vs 70% open -> 90% vs 80% (weighted) -> closed wins
        OPEN_ISSUE_BOOST = 0.10  # 10% boost for open issues
        filtered_results.sort(
            key=lambda x: -(x['similarity'] + (OPEN_ISSUE_BOOST if x['is_open'] else 0))
        )

        # Limit to top_k (max 2) results
        filtered_results = filtered_results[:top_k]
        
        # Format output
        output_lines = [
            f"Found {len(filtered_results)} similar issue(s) based on semantic analysis:",
            f"(Showing issues with similarity >= {similarity_threshold:.2f})",
            ""
        ]
        
        for i, result in enumerate(filtered_results, 1):
            metadata = result['metadata']
            
            # Parse JSON fields
            labels = json.loads(metadata.get('labels', '[]'))
            components = json.loads(metadata.get('components', '[]'))
            
            # Format similarity percentage
            similarity_pct = result['similarity'] * 100
            
            # Create similarity bar visualization
            bar_length = int(similarity_pct / 10)
            similarity_bar = '█' * bar_length + '░' * (10 - bar_length)
            
            # Determine open/closed indicator
            is_open = result.get('is_open', True)
            status_indicator = "🔴 OPEN" if is_open else "🟢 CLOSED"

            issue_info = f"""
{'='*70}
#{i} - {metadata.get('key', 'N/A')} [{status_indicator}] ({similarity_pct:.1f}% match) {similarity_bar}
{'='*70}
Summary: {metadata.get('summary', 'N/A')}
Status: {metadata.get('status', 'N/A')} | Type: {metadata.get('issuetype', 'N/A')} | Priority: {metadata.get('priority', 'N/A')}
Resolution: {metadata.get('resolution', 'Unresolved')}
Created: {metadata.get('created', 'N/A')[:10]} | Updated: {metadata.get('updated', 'N/A')[:10]}
URL: {metadata.get('url', 'N/A')}
"""
            output_lines.append(issue_info)
        
        output_lines.append("")
        output_lines.append("💡 Recommendation:")
        
        # Provide intelligent recommendations based on results
        best_match = filtered_results[0]
        best_similarity = best_match['similarity'] * 100
        
        if best_similarity >= 90:
            output_lines.append(
                f"   • Very high similarity ({best_similarity:.1f}%) - This appears to be the same or nearly identical issue."
            )
            output_lines.append(f"   • Consider updating issue {best_match['key']} instead of creating a new one.")
        elif best_similarity >= 80:
            output_lines.append(
                f"   • High similarity ({best_similarity:.1f}%) - Review {best_match['key']} before creating a new issue."
            )
            output_lines.append("   • The root cause may be related or identical.")
        else:
            output_lines.append(
                f"   • Moderate similarity ({best_similarity:.1f}%) - Related issues exist but may not be identical."
            )
            output_lines.append("   • Review these issues for context, but a new issue may be warranted.")
        
        return '\n'.join(output_lines)
        
    except Exception as e:
        return f"Error searching for similar Jira issues: {str(e)}"

TOOLS = [
    get_text_from_file,
    get_failed_testsuites,
    analyze_screenshot_visual_confirmation,
    get_immediate_log_files_content,
    get_folder_structure,
    get_immediate_directories,
    get_immediate_files,
    check_file_exists,
    create_jira_bug,
    search_similar_jira_issues,
]