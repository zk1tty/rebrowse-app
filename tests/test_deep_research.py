import pdb

from dotenv import load_dotenv

load_dotenv()
import sys

sys.path.append(".")
import asyncio
import os
import sys
from pprint import pprint
from uuid import uuid4
from src.utils import utils
from src.agent.custom_agent import CustomAgent
import json
from browser_use.agent.service import Agent
from browser_use.browser.browser import BrowserConfig, Browser
from langchain.schema import SystemMessage, HumanMessage
from json_repair import repair_json
from src.agent.custom_prompts import CustomSystemPrompt, CustomAgentMessagePrompt
from src.controller.custom_controller import CustomController


async def deep_research():
    # define task
    task = "Write a report on RPA (Robotic Process Automation) technology in English, from all espects, more than 2,000 words"
    task_id = uuid4().__str__()
    save_dir = os.path.join(f"./tmp/deep_research/{task_id}")
    os.makedirs(save_dir, exist_ok=True)

    llm = utils.get_llm_model(provider="gemini", model_name="gemini-2.0-flash-thinking-exp-01-21", temperature=0.7)
    # llm = utils.get_llm_model(provider="deepseek", model_name="deepseek-reasoner", temperature=0.7)
    llm_bu = utils.get_llm_model(provider="azure_openai", model_name="gpt-4o", temperature=0.7)

    # 搜索的LLM历史信息
    max_query_num = 3
    search_system_prompt = """
    You are a **Deep Researcher**, an AI agent specializing in in-depth information gathering and research using a web browser with **automated execution capabilities**. Your expertise lies in formulating comprehensive research plans and executing them meticulously to fulfill complex user requests. You will analyze user instructions, devise a detailed research plan, and determine the necessary search queries to gather the required information.

    **Your Task:**

    Given a user's research topic, you will:

    1. **Develop a Research Plan:** Outline the key aspects and subtopics that need to be investigated to thoroughly address the user's request. This plan should be a high-level overview of the research direction.
    2. **Generate Search Queries:** Based on your research plan, generate a list of specific search queries to be executed in a web browser. These queries should be designed to efficiently gather relevant information for each aspect of your plan.

    **Output Format:**

    Your output will be a JSON object with the following structure:

    ```json
    {
    "plan": "A concise, high-level research plan outlining the key areas to investigate.",
      "queries": [
        "search query 1",
        "search query 2",
        //... up to a maximum of 3 search queries
      ]
    }
    ```

    **Important:**

    *   Limit your output to a **maximum of 3** search queries.
    *   Make the search queries to help the automated agent find the needed information. Consider what keywords are most likely to lead to useful results.
    *   If you have gathered for all the information you want and no further search queries are required, output queries with an empty list: `[]`
    *   Make sure output search queries are different from the history queries.

    **Inputs:**

    1.  **User Instruction:** The original instruction given by the user.
    2.  **Previous Queries:** History Queries.
    3.  **Previous Search Results:** Textual data gathered from prior search queries. If there are no previous search results this string will be empty.
    """
    search_messages = [SystemMessage(content=search_system_prompt)]

    # 记录和总结的历史信息，保存到raw_infos
    record_system_prompt = """
    You are an expert information recorder. Your role is to process user instructions, current search results, and previously recorded information to extract, summarize, and record new, useful information that helps fulfill the user's request. Your output will be a JSON formatted list, where each element represents a piece of extracted information and follows the structure: `{"url": "source_url", "title": "source_title", "summary_content": "concise_summary", "thinking": "reasoning"}`.

**Important Considerations:**

1. **Minimize Information Loss:** While concise, prioritize retaining important details and nuances from the sources. Aim for a summary that captures the essence of the information without over-simplification.

2. **Avoid Redundancy:** Do not record information that is already present in the Previous Recorded Information. Check for semantic similarity, not just exact matches. However, if the same information is expressed differently in a new source and this variation adds valuable context or clarity, it should be included.

3. **Utility Focus:** Only record information that is likely to be useful for completing the user's original instruction. Ask yourself: "How might this information contribute to the AI agent achieving its goal?" Prefer more information over less, as long as it remains relevant to the user's request.

4. **Source Information:** Extract and include the source title and URL for each piece of information summarized. This is crucial for verification and context. If a piece of information cannot be attributed to a specific source from the provided search results, use `"url": "unknown"` and `"title": "unknown"`.

5. **Thinking and Report Structure:**  For each extracted piece of information, add a `"thinking"` key. This field should contain your assessment of how this information could be used in a report, which section it might belong to (e.g., introduction, background, analysis, conclusion, specific subtopics), and any other relevant thoughts about its significance or connection to other information.

**Output Format:**

Provide your output as a JSON formatted list. Each item in the list must adhere to the following format:

```json
[
  {
    "url": "source_url_1",
    "title": "source_title_1",
    "summary_content": "concise_summary_of_content_from_source_1",
    "thinking": "This could be used in the introduction to set the context. It also relates to the section on the history of the topic."
  },
  // ... more entries
  {
    "url": "unknown",
    "title": "unknown",
    "summary_content": "concise_summary_of_content_without_clear_source",
    "thinking": "This might be useful background information, but I need to verify its accuracy. Could be used in the methodology section to explain how data was collected."
  }
]
```

**Inputs:**

1. **User Instruction:** The original instruction given by the user. This helps you determine what kind of information will be useful and how to structure your thinking.
2. **Previous Recorded Information:** Textual data gathered and recorded from previous searches and processing, represented as a single text string.
3. **Current Search Results:** Textual data gathered from the most recent search query.
    """
    record_messages = [SystemMessage(content=record_system_prompt)]

    browser = Browser(
        config=BrowserConfig(
            disable_security=True,
            headless=False,  # Set to False to see browser actions
        )
    )
    controller = CustomController()

    search_iteration = 0
    max_search_iterations = 4  # Limit search iterations to prevent infinite loop
    use_vision = False

    history_query = []
    history_infos = []
    try:
        while search_iteration < max_search_iterations:
            search_iteration += 1
            print(f"Start {search_iteration}th Search...")
            history_queries = ""
            for i in range(len(history_query)):
                history_queries += f"{i + 1}. {history_query[i]}\n"
            history_infos_ = json.dumps(history_infos, indent=4)
            query_prompt = f"User Instruction:{task} \n Previous Queries: {history_queries} \n Previous Search Results:\n {history_infos_}"
            search_messages.append(HumanMessage(content=query_prompt))
            ai_query_msg = llm.invoke(search_messages[:1] + search_messages[1:][-1:])
            if hasattr(ai_query_msg, "reasoning_content"):
                print("🤯 Start Search Deep Thinking: ")
                print(ai_query_msg.reasoning_content)
                print("🤯 End Search Deep Thinking")
            ai_query_content = ai_query_msg.content.replace("```json", "").replace("```", "")
            ai_query_content = repair_json(ai_query_content)
            ai_query_content = json.loads(ai_query_content)
            query_plan = ai_query_content["plan"]
            print("Current Planing:")
            print(query_plan)
            query_tasks = ai_query_content["queries"]
            if not query_tasks:
                break
            else:
                history_query.extend(query_tasks)
                print("Query tasks:")
                print(query_tasks)
                search_messages.append(ai_query_msg)

            # 2. Perform Web Search and Auto exec
            agents = [CustomAgent(
                task=task + ". Please click on the most relevant link to get information and go deeper, instead of just staying on the search page.",
                llm=llm_bu,
                browser=browser,
                use_vision=use_vision,
                system_prompt_class=CustomSystemPrompt,
                agent_prompt_class=CustomAgentMessagePrompt,
                max_actions_per_step=5,
                controller=controller
            ) for task in query_tasks]
            query_results = await asyncio.gather(*[agent.run(max_steps=5) for agent in agents])

            # 3. Summarize Search Result
            query_result_dir = os.path.join(save_dir, "query_results")
            os.makedirs(query_result_dir, exist_ok=True)
            for i in range(len(query_tasks)):
                query_result = query_results[i].final_result()
                with open(os.path.join(query_result_dir, f"{search_iteration}-{i}.md"), "w") as fw:
                    fw.write(f"Query: {query_tasks[i]}\n")
                    fw.write(query_result)
                history_infos_ = json.dumps(history_infos, indent=4)
                record_prompt = f"User Instruction:{task}. \nPrevious Recorded Information:\n {json.dumps(history_infos_)} \n Current Search Results: {query_result}\n "
                record_messages.append(HumanMessage(content=record_prompt))
                ai_record_msg = llm.invoke(record_messages[:1] + record_messages[-1:])
                if hasattr(ai_record_msg, "reasoning_content"):
                    print("🤯 Start Record Deep Thinking: ")
                    print(ai_record_msg.reasoning_content)
                    print("🤯 End Record Deep Thinking")
                record_content = ai_record_msg.content
                record_content = repair_json(record_content)
                new_record_infos = json.loads(record_content)
                history_infos.extend(new_record_infos)
                record_messages.append(ai_record_msg)

        print("\nFinish Searching, Start Generating Report...")

        # 5. Report Generation in Markdown (or JSON if you prefer)
        writer_system_prompt = """
        You are a professional report writer tasked with creating polished, high-quality reports that fully meet the user's needs, based on the user's instructions and the relevant information provided. You will write the report using Markdown format, ensuring it is both informative and visually appealing.

**Specific Instructions:**

*   **Structure for Impact:** The report must have a clear, logical, and impactful structure. Begin with a compelling introduction that immediately grabs the reader's attention. Develop well-structured body paragraphs that flow smoothly and logically, and conclude with a concise and memorable conclusion that summarizes key takeaways and leaves a lasting impression.
*   **Engaging and Vivid Language:** Employ precise, vivid, and descriptive language to make the report captivating and enjoyable to read. Use stylistic techniques to enhance engagement. Tailor your tone, vocabulary, and writing style to perfectly suit the subject matter and the intended audience to maximize impact and readability.
*   **Accuracy, Credibility, and Citations:** Ensure that all information presented is meticulously accurate, rigorously truthful, and robustly supported by the available data. **Cite sources exclusively using bracketed sequential numbers within the text (e.g., [1], [2], etc.). If no references are used, omit citations entirely.** These numbers must correspond to a numbered list of references at the end of the report.
*   **Publication-Ready Formatting:** Adhere strictly to Markdown formatting for excellent readability and a clean, highly professional visual appearance. Pay close attention to formatting details like headings, lists, emphasis, and spacing to optimize the visual presentation and reader experience. The report should be ready for immediate publication upon completion, requiring minimal to no further editing for style or format.
*   **Conciseness and Clarity (Unless Specified Otherwise):** When the user does not provide a specific length, prioritize concise and to-the-point writing, maximizing information density while maintaining clarity.
*   **Length Adherence:** When the user specifies a length constraint, meticulously stay within reasonable bounds of that specification, ensuring the content is appropriately scaled without sacrificing quality or completeness.
*   **Comprehensive Instruction Following:** Pay meticulous attention to all details and nuances provided in the user instructions. Strive to fulfill every aspect of the user's request with the highest degree of accuracy and attention to detail, creating a report that not only meets but exceeds expectations for quality and professionalism.
*   **Reference List Formatting:** The reference list at the end must be formatted as follows: `[1] Title (URL, if available)`.
*   **ABSOLUTE FINAL OUTPUT RESTRICTION:**  **Your output must contain ONLY the finished, publication-ready Markdown report. Do not include ANY extraneous text, phrases, preambles, meta-commentary, or markdown code indicators (e.g., "```markdown```"). The report should begin directly with the title and introductory paragraph, and end directly after the conclusion and the reference list (if applicable).**  **Your response will be deemed a failure if this instruction is not followed precisely.**
        
**Inputs:**

1. **User Instruction:** The original instruction given by the user. This helps you determine what kind of information will be useful and how to structure your thinking.
3. **Search Information:** Information gathered from the recent search queries.
        """
        with open(os.path.join(save_dir, "record_infos.json"), "w") as fw:
            json.dump(history_infos, fw)
        history_infos_ = json.dumps(history_infos, indent=4)
        report_prompt = f"User Instruction:{task} \n Search Information:\n {history_infos_}"
        report_messages = [SystemMessage(content=writer_system_prompt),
                           HumanMessage(content=report_prompt)]  # New context for report generation
        ai_report_msg = llm.invoke(report_messages)
        if hasattr(ai_report_msg, "reasoning_content"):
            print("🤯 Start Report Deep Thinking: ")
            print(ai_report_msg.reasoning_content)
            print("🤯 End Report Deep Thinking")
        report_content = ai_report_msg.content

        if report_content:
            report_file_path = os.path.join(save_dir, "final_report.md")
            with open(report_file_path, "w", encoding="utf-8") as f:
                f.write(report_content)
            print(f"报告已生成并保存到: {report_file_path}")

        else:
            print("未能生成报告内容。")

    except Exception as e:
        print(f"Deep research 过程中发生错误: {e}")
    finally:
        if browser:
            await browser.close()
            print("Browser closed.")


if __name__ == "__main__":
    asyncio.run(deep_research())
