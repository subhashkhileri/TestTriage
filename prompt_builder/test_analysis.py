from utils.storage import storage_client

def get_e2e_test_analysis_prompt(base_dir: str) -> str:
    job_name = base_dir.split("/")[1]
    print(job_name)
    e2e_job_dir = [dir for dir in storage_client.get_immediate_directories(f"{base_dir}/artifacts/") if dir.startswith("e2e-tests-")][0]
    print(e2e_job_dir)
    e2e_step_registory_dir = [dir for dir in storage_client.get_immediate_directories(f"{base_dir}/artifacts/{e2e_job_dir}/") if dir.endswith("-nightly")]
    e2e_step_registory_dir = e2e_step_registory_dir[0] if e2e_step_registory_dir else None
    print(e2e_step_registory_dir)
    e2e_playwright_projects_result_dirs = [dir for dir in storage_client.get_immediate_directories(f"{base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registory_dir}/artifacts/")]
    print(e2e_playwright_projects_result_dirs)
    build_log_path = f"{base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registory_dir}/build-log.txt"
    print(build_log_path)


# --- Define file paths and initial query (as in the original script) ---
    test_analysis_prompts = []
    if not e2e_step_registory_dir:
        all_e2e_step_registory_dir = [dir for dir in storage_client.get_immediate_directories(f"{base_dir}/artifacts/{e2e_job_dir}/")]
        print(all_e2e_step_registory_dir)
        for e2e_step_registory in all_e2e_step_registory_dir:
            build_log_path = f"{base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registory}/build-log.txt"
            if storage_client.blob_exists(build_log_path):
                test_analysis_prompts.append(f"""Analyze build log from {build_log_path} using get_text_from_file tool.""")
        return "CI Job Failed during setup registry setup (multiple attempts):\n".join(test_analysis_prompts)
    
    for index, playwright_project_result_dir in enumerate(e2e_playwright_projects_result_dirs):
        junit_xml_path = f"{base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registory_dir}/artifacts/{playwright_project_result_dir}/junit-results.xml"

        if storage_client.bucket.blob(junit_xml_path).exists():
            screenshot_base_dir = f"{base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registory_dir}/artifacts/{playwright_project_result_dir}/test-results/"
            test_analysis_prompts.append(f"""
{index+1}. **For Each Failure in JUnit XML ({playwright_project_result_dir})**:
    1. **Identify Failure**: Use `get_failed_testsuites` to read and parse `{junit_xml_path}` for failure messages and screenshot paths. Report screenshot path if found.
    2. **Root Cause Analysis (Mandatory)**:
        a. Construct the full `image_path` by joining `"{screenshot_base_dir}"` with the relative path.
        b. Prepare `test_analysis_text`: a concise summary including the test's purpose and failure message.
        c. **You MUST call for each failure in JUnit XML** `analyze_screenshot_visual_confirmation(image_path=full_image_path, test_failure_analysis_text=test_analysis_text, test_title=test_title, junit_xml_failure=junit_xml_failure)`.
        d. Integrate the response. If error (e.g., image not found), report it.
        e. Return the exact root cause analysis from analyze_screenshot_visual_confirmation.

    3. **Test Purpose**: Describe what the test was trying to verify.
""")
        else:
            pod_logs_dir = f"{base_dir}/artifacts/{e2e_job_dir}/{e2e_step_registory_dir}/artifacts/{playwright_project_result_dir}/"
            test_analysis_prompts.append(f"""
{index+1}. No Test executions found for playwright project: {playwright_project_result_dir}.
""")
            if 'pod_logs' in storage_client.get_immediate_directories(pod_logs_dir):
                test_analysis_prompts.append(f"""
Mandatory: Analyze pod logs from "{pod_logs_dir}pod_logs/" for playwright project: {playwright_project_result_dir} using get_immediate_log_files_content tool(prefix="{pod_logs_dir}pod_logs/").
""")
            else:
                test_analysis_prompts.append(f"""\nAnalyze build log from {build_log_path} using get_text_from_file tool.""")
   
    test_analysis_prompts.append(f"""No project-specific artifacts found. Analyze build log from {build_log_path} using get_text_from_file tool.""") if not test_analysis_prompts and storage_client.bucket.blob(build_log_path).exists() else None

    test_analysis_prompt = "Analysis Process for EACH Failed Test Case (from JUnit XML) or Project Issue:" + "\n".join(test_analysis_prompts)

    initial_user_query = f"""
You are an AI expert in test automation analysis. Your goal is to analyze Playwright test failures based on available artifacts.
You MUST use the provided tools to gather information. Do NOT attempt to access files directly or assume content is pre-loaded.
Test failure log URL from the prow link: https://prow.ci.openshift.org/view/gs/test-platform-results/"{base_dir}

Available Tools:
- `get_failed_testsuites(xml_file_prefix: str)`: Use this to read specific file like JUnit XML.
- `get_text_from_file(file_path: str)`: Use this to read specific, smaller files.
- `analyze_screenshot_visual_confirmation(image_path: str, test_failure_analysis_text: str, test_title: str, junit_xml_failure: str)`: Use this to analyze a screenshot. Provide the image path and a summary of the test failure (purpose, failure message, your current analysis). The tool will return a visual confirmation or insight based on the image.
- `get_immediate_log_files_content(prefix: str)`: Use this to read the content of all immediate .log files from the given prefix.

{test_analysis_prompt}

For each failed test case, structure your response as follows:

    1. Test Case: [Test Case Name]
        a. Test Purpose: [Description]
        b. Failure Message: [From JUnit XML]
        c. Root Cause Analysis: [Root Cause Analysis]
        d. Actionable Recommendations: [Solutions max 2]

For CI/Build failures or pod log issues, structure your response as follows:

    1. Issue Type: [CI Failure/Build Failure/Pod Log Issue]
        a. Issue Description: [Summary of the problem]
        b. Failure Details: [Key error messages and symptoms]
        c. Root Cause Analysis: [Analysis based on logs]
        d. Actionable Recommendations: [Solutions max 2]

Start your analysis.
"""
    print(initial_user_query)
    return initial_user_query