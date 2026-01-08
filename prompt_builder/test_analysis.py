from typing import List, Optional
from pathlib import Path
from utils.storage import storage_client


class E2ETestAnalysisBuilder:
    """Builder class for creating E2E test analysis prompts."""
    
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.job_name = self._extract_job_name()
        
    def _extract_job_name(self) -> str:
        """Extract job name from base directory path."""
        return self.base_dir.split("/")[1]
    
    def _get_e2e_job_directory(self) -> Optional[str]:
        """Get the E2E job directory from artifacts."""
        artifacts_path = f"{self.base_dir}/artifacts/"
        directories = storage_client.get_immediate_directories(artifacts_path)
        e2e_dirs = [dir for dir in directories if dir.startswith("e2e-")]
        return e2e_dirs[0] if e2e_dirs else None
    
    def _get_e2e_step_registry_directory(self, e2e_job_dir: str) -> Optional[str]:
        """Get the E2E step registry directory."""
        step_path = f"{self.base_dir}/artifacts/{e2e_job_dir}/"
        directories = storage_client.get_immediate_directories(step_path)
        nightly_dirs = [dir for dir in directories if dir.endswith("-nightly")]
        return nightly_dirs[0] if nightly_dirs else None
    
    def _get_playwright_project_directories(self, e2e_job_dir: str, e2e_step_registry_dir: str) -> List[str]:
        """Get Playwright project result directories."""
        artifacts_path = f"{self.base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registry_dir}/artifacts/"
        directories = storage_client.get_immediate_directories(artifacts_path)
        return [dir for dir in directories if "reporting" not in dir]
    
    def _get_build_log_path(self, e2e_job_dir: str, e2e_step_registry_dir: str) -> str:
        """Construct build log path."""
        return f"{self.base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registry_dir}/build-log.txt"
    
    def _build_failed_step_registry_prompt(self, e2e_job_dir: str) -> str:
        """Build prompt for failed step registry."""
        all_step_dirs = storage_client.get_immediate_directories(f"{self.base_dir}/artifacts/{e2e_job_dir}/")
        prompts = []

        for index, step_dir in enumerate(all_step_dirs):
            build_log_path = f"{self.base_dir}/artifacts/{e2e_job_dir}/{step_dir}/build-log.txt"
            if storage_client.blob_exists(build_log_path):
                prompts.append(f"{index+1}. {step_dir}: Analyze build log from {build_log_path} using get_text_from_file tool.")

        prompts.append("""
After analyzing the build logs and identifying the root cause:
- Create a comprehensive `failure_description` summarizing your findings
- You MUST call `search_similar_jira_issues(failure_description=..., error_message=...)` to find similar issues
- **CRITICAL**: NEVER invent, guess, or hallucinate Jira issue IDs. Only report issues ACTUALLY returned by the tool.
- If the tool returns no similar issues, report: "No similar Jira issues found in the database."
""")

        return "CI Job Failed during step registry analysis the following logs:\n" + "\n".join(prompts)
    
    def _build_playwright_project_prompt(self, index: int, project_dir: str, e2e_job_dir: str, 
                                       e2e_step_registry_dir: str, build_log_path: str) -> str:
        """Build prompt for a specific Playwright project."""
        junit_xml_path = f"{self.base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registry_dir}/artifacts/{project_dir}/junit-results.xml"
        
        if storage_client.bucket.blob(junit_xml_path).exists():
            screenshot_base_dir = f"{self.base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registry_dir}/artifacts/{project_dir}/test-results/"
            return f"""
{index+1}. **For Each Failure in JUnit XML ({project_dir})**:
    1. **Identify Failure**: Use `get_failed_testsuites` to read and parse `{junit_xml_path}` for failure messages and screenshot paths. Report screenshot path if found.
    2. **Root Cause Analysis (Mandatory)**:
        a. Construct the full `image_path` by joining `"{screenshot_base_dir}"` with the relative path.
        b. Prepare `test_analysis_text`: a concise summary including the test's purpose and failure message.
        c. **You MUST call for each failure in JUnit XML** `analyze_screenshot_visual_confirmation(image_path=full_image_path, test_failure_analysis_text=test_analysis_text, test_title=test_title, junit_xml_failure=junit_xml_failure)`.
        d. Integrate the response. If error (e.g., image not found), report it.
        e. Return the exact root cause analysis from analyze_screenshot_visual_confirmation.

    3. Find Similar Jira Issues (Mandatory - NEVER HALLUCINATE):
        a. After completing the Root Cause Analysis, create a comprehensive `failure_description` summarizing your findings.
        b. You MUST call `search_similar_jira_issues` for each failure, providing the `test_name`, the `error_message` from the JUnit XML, and your generated `failure_description`.
        c. **CRITICAL**: You MUST wait for the tool to return actual results. NEVER invent, guess, or hallucinate Jira issue IDs or summaries.
        d. If the tool returns no similar issues or an error, report that honestly - do NOT make up fake issues.
"""
        else:
            return self._build_no_execution_prompt(index, project_dir, e2e_job_dir, 
                                                 e2e_step_registry_dir, build_log_path)
    
    def _build_no_execution_prompt(self, index: int, project_dir: str, e2e_job_dir: str,
                                 e2e_step_registry_dir: str, build_log_path: str) -> str:
        """Build prompt for projects with no test executions."""
        prompt_parts = [f"\n{index+1}. No Test executions found for playwright project: {project_dir}."]

        pod_logs_dir = f"{self.base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registry_dir}/artifacts/{project_dir}/"
        directories = storage_client.get_immediate_directories(pod_logs_dir)

        if 'pod_logs' in directories:
            prompt_parts.append(f"""
Mandatory: Analyze pod logs from "{pod_logs_dir}pod_logs/" for playwright project: {project_dir} using get_immediate_log_files_content tool(prefix="{pod_logs_dir}pod_logs/").
""")
        else:
            prompt_parts.append(f"\nAnalyze build log from {build_log_path} using get_text_from_file tool.")

        # Add instruction to search for similar Jira issues
        prompt_parts.append("""
After analyzing the logs and identifying the root cause:
- You MUST call `search_similar_jira_issues(failure_description=..., error_message=...)` to find similar issues
- **CRITICAL**: NEVER invent or hallucinate Jira issue IDs. Only report issues ACTUALLY returned by the tool.
""")

        return "".join(prompt_parts)
    
    def _build_final_prompt(self, test_analysis_prompts: List[str], build_log_path: str) -> str:
        """Build the final analysis prompt."""
        if not test_analysis_prompts and storage_client.bucket.blob(build_log_path).exists():
            test_analysis_prompts.append(f"""No project-specific artifacts found. Analyze build log from {build_log_path} using get_text_from_file tool.

After analyzing the build log and identifying the root cause:
- You MUST call `search_similar_jira_issues(failure_description=..., error_message=...)` to find similar issues
- **CRITICAL**: NEVER invent or hallucinate Jira issue IDs. Only report issues ACTUALLY returned by the tool.
- If the tool returns no results, write: "No similar Jira issues found in the database."
""")
        
        test_analysis_prompt = "Analysis Process for EACH Failed Test Case (from JUnit XML) or Project Issue:" + "\n".join(test_analysis_prompts)
        
        return f"""
You are an AI expert in test automation analysis. Your goal is to analyze Playwright test failures based on available artifacts.
You MUST use the provided tools to gather information. Do NOT attempt to access files directly or assume content is pre-loaded.
Test failure log URL from the prow link: https://prow.ci.openshift.org/view/gs/test-platform-results/"{self.base_dir}

**⚠️ CRITICAL RULE: MANDATORY TOOL CALLS FOR JIRA ISSUES ⚠️**
Before you can include a "Similar Jira Issues" section in your response, you MUST:
1. **FIRST** call `search_similar_jira_issues` tool - this is NON-NEGOTIABLE
2. **WAIT** for the tool to return results
3. **ONLY THEN** format and include the results in your response
4. If the tool returns no issues, write: "No similar Jira issues found in the database."

You CANNOT skip the tool call and go directly to the output. The tool call MUST happen.
NEVER invent, fabricate, or hallucinate Jira issue IDs - this is STRICTLY FORBIDDEN.

Available Tools:
- `get_failed_testsuites(xml_file_prefix: str)`: Use this to read specific file like JUnit XML.
- `get_text_from_file(file_path: str)`: Use this to read specific, smaller files.
- `analyze_screenshot_visual_confirmation(image_path: str, test_failure_analysis_text: str, test_title: str, junit_xml_failure: str)`: **MANDATORY for each failure.** This returns a comprehensive 2-3 sentence Root Cause Analysis paragraph that starts with "The root cause is..." and includes visual evidence/error analysis. You MUST insert this output directly into the "Root Cause Analysis" section without modification.
- `get_immediate_log_files_content(prefix: str)`: Use this to read the content of all immediate .log files from the given prefix.
- `search_similar_jira_issues(failure_description: str, test_name: str, error_message: str)`: **MANDATORY for each failure.** Returns up to 2 most similar issues from ChromaDB, prioritizing open issues. **CRITICAL: You MUST actually call this tool and wait for results. NEVER guess or make up Jira issue IDs or summaries - only use the exact issues returned by the tool.** If the tool returns "No similar issues found", report that fact - do NOT invent fake issues.

{test_analysis_prompt}

**CRITICAL: You MUST follow this EXACT format for EVERY failed test case. Do NOT deviate from this structure:**

*[Number]. Test Case: [Full Test Case Name]*

• *Failure Message:* `[Exact error message from JUnit XML - use backticks for code formatting]`
• *Root Cause Analysis:* [Insert the exact output from analyze_screenshot_visual_confirmation - a comprehensive 2-3 sentence paragraph that starts with "The root cause is..." and includes visual evidence/error analysis]
• *Actionable Recommendations:*
  1. [First specific, actionable fix]
  2. [Second specific, actionable fix - if applicable]
• *Similar Jira Issues:* [max 2 issues, open issues prioritized]
  - [🔴 or 🟢 if issue is open or closed] *<https://issues.redhat.com/browse/ISSUE-KEY|ISSUE-KEY>:* "[Issue summary]" - [Brief relevance explanation]

**For CI/Build/Step Registry failures or pod log issues, use this EXACT format:**

*[Number]. Issue Type: [CI Failure/Build Failure/Pod Log Issue]*

• *Issue Description:* [One sentence summary of the problem]
• *Failure Details:* [Key error messages and symptoms - use backticks for error text]
• *Root Cause Analysis:* [Detailed analysis based on logs - identify the specific cause]
• *Actionable Recommendations:*
  1. [First specific, actionable fix]
  2. [Second specific, actionable fix - if applicable]
• *Similar Jira Issues:* [max 2 issues, open issues prioritized]
  - [🔴 or 🟢 if issue is open or closed] *<https://issues.redhat.com/browse/ISSUE-KEY|ISSUE-KEY>:* "[Issue summary]" - [Brief relevance explanation]

**IMPORTANT FORMATTING RULES:**
1. *Consistency is critical* - Use the EXACT same format for every single test failure
2. Use Slack-compatible formatting:
   - Use `•` (bullet point) for main items, NOT `*`
   - Use `-` (dash) for sub-items
   - Use single `*asterisks*` for bold text (Slack mrkdwn format)
   - Use backticks for code/error messages
3. The output from `analyze_screenshot_visual_confirmation` is a comprehensive 2-3 sentence paragraph - insert it directly after "Root Cause Analysis:" without any modifications or additional formatting
4. For "Similar Jira Issues":
   - **MANDATORY SEQUENCE**: You MUST call `search_similar_jira_issues` tool FIRST, then format the returned results
   - You CANNOT write the Similar Jira Issues section without first making the tool call
   - Parse the tool output and format each issue as: *<https://issues.redhat.com/browse/ISSUE-KEY|ISSUE-KEY>:* "[Summary]" - [Why it's relevant]
   - The ISSUE-KEY must be a clickable Slack link using the format: <https://issues.redhat.com/browse/ISSUE-KEY|ISSUE-KEY>
   - If the tool returns "No similar issues found" or an error, write: "No similar Jira issues found in the database."
   - Do NOT include match percentage in the final output
   - **NEVER skip the tool call - it is required before you can output anything about Jira issues**
5. Use numbered format for test cases: "*1. Test Case:*", "*2. Test Case:*", etc.
6. Keep recommendations concise - maximum 2 actionable items

7. *Multiple Failures Analysis - Cross-Reference Detection:*
   - If analyzing multiple test failures, look for patterns
   - If 2+ failures share the same root cause (e.g., same locator issue, same timeout, same API failure), note it
   - If patterns exist, add a section before the final prompt:

   *Cross-Failure Patterns Detected:*
   • [Pattern description] affects tests: [Test 1], [Test 2], [Test 3]
   • [Another pattern] indicates [system-wide issue]

8. *Final Prompt for Jira Issue Creation:*
   - After completing ALL failure analysis, review which failures do NOT have an open (🔴) Jira issue
   - At the very END of your response, add this section ONLY if there are failures without open issues:

   ---
   *Would you like me to create Jira issues for the following failures which don't have open Jira issues?*
   • Failure 1 [test title]
   • Failure 2 [test title]

   [Only list failures that have no open Jira issues.]

Start your analysis.
"""
    
    def build_prompt(self) -> str:
        """Build the complete E2E test analysis prompt."""
        e2e_job_dir = self._get_e2e_job_directory()
        if not e2e_job_dir:
            return "No E2E job directory found."
        
        e2e_step_registry_dir = self._get_e2e_step_registry_directory(e2e_job_dir)
        build_log_path = self._get_build_log_path(e2e_job_dir, e2e_step_registry_dir or "")
        
        if not e2e_step_registry_dir:
            return self._build_failed_step_registry_prompt(e2e_job_dir)
        
        playwright_project_dirs = self._get_playwright_project_directories(e2e_job_dir, e2e_step_registry_dir)
        test_analysis_prompts = []
        
        for index, project_dir in enumerate(playwright_project_dirs):
            prompt = self._build_playwright_project_prompt(index, project_dir, e2e_job_dir, 
                                                         e2e_step_registry_dir, build_log_path)
            test_analysis_prompts.append(prompt)
        
        return self._build_final_prompt(test_analysis_prompts, build_log_path)


def get_e2e_test_analysis_prompt(base_dir: str) -> str:
    """Generate E2E test analysis prompt for given base directory."""
    builder = E2ETestAnalysisBuilder(base_dir)
    return builder.build_prompt()
