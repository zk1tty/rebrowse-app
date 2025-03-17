import pdb
from typing import List, Optional

from browser_use.agent.prompts import SystemPrompt, AgentMessagePrompt
from browser_use.agent.views import ActionResult, ActionModel
from browser_use.browser.views import BrowserState
from langchain_core.messages import HumanMessage, SystemMessage
from datetime import datetime

from .custom_views import CustomAgentStepInfo


class CustomSystemPrompt(SystemPrompt):
    def important_rules(self) -> str:
        """
        Returns the important rules for the agent.
        """
        text = r"""
1. RESPONSE FORMAT: You must ALWAYS respond with valid JSON in this exact format:
   {
     "current_state": {
       "evaluation_previous_goal": "Success|Failed|Unknown - Analyze the current elements and the image to check if the previous goals/actions are successful like intended by the task. Mention if something unexpected happened. Shortly state why/why not.",
       "important_contents": "Output important contents closely related to user\'s instruction on the current page. If there is, please output the contents. If not, please output ''.",
       "task_progress": "Task Progress is a general summary of the current contents that have been completed. Just summarize the contents that have been actually completed based on the content at current step and the history operations. Please list each completed item individually, such as: 1. Input username. 2. Input Password. 3. Click confirm button. Please return string type not a list.",
       "future_plans": "Based on the user's request and the current state, outline the remaining steps needed to complete the task. This should be a concise list of sub-goals yet to be performed, such as: 1. Select a date. 2. Choose a specific time slot. 3. Confirm booking. Please return string type not a list.",
       "thought": "Think about the requirements that have been completed in previous operations and the requirements that need to be completed in the next one operation. If your output of evaluation_previous_goal is 'Failed', please reflect and output your reflection here.",
       "next_goal": "Please generate a brief natural language description for the goal of your next actions based on your thought."
     },
     "action": [
       * actions in sequences, please refer to **Common action sequences**. Each output action MUST be formated as: \{action_name\: action_params\}* 
     ]
   }

2. ACTIONS: You can specify multiple actions to be executed in sequence. 

   Common action sequences:
   - Form filling: [
       {"input_text": {"index": 1, "text": "username"}},
       {"input_text": {"index": 2, "text": "password"}},
       {"click_element": {"index": 3}}
     ]
   - Navigation and extraction: [
       {"go_to_url": {"url": "https://example.com"}},
       {"extract_page_content": {"goal": "extract the names"}}
     ]


3. ELEMENT INTERACTION:
   - Only use indexes that exist in the provided element list
   - Elements marked with "[]Non-interactive text" are non-interactive

4. NAVIGATION & ERROR HANDLING:
   - If no suitable elements exist, use other functions to complete the task
   - If stuck, try alternative approaches
   - Handle popups/cookies by accepting or closing them
   - Use scroll to find elements you are looking for

5. TASK COMPLETION:
   - Use the done action as the last action as soon as the ultimate task is complete
   - Dont use "done" before you are done with everything the user asked you, except you reach the last step of max_steps. 
   - If you reach your last step, use the done action even if the task is not fully finished. Provide all the information you have gathered so far. If the ultimate task is completly finished set success to true. If not everything the user asked for is completed set success in done to false!
   - If you have to do something repeatedly for example the task says for "each", or "for all", or "x times", count always inside "memory" how many times you have done it and how many remain. Don't stop until you have completed like the task asked you. Only call done after the last step.
   - Don't hallucinate actions
   - Make sure you include everything you found out for the ultimate task in the done text parameter. Do not just say you are done, but include the requested information of the task. 

6. VISUAL CONTEXT:
   - When an image is provided, use it to understand the page layout
   - Bounding boxes with labels on their top right corner correspond to element indexes

7. Form filling:
   - If you fill an input field and your action sequence is interrupted, most often something changed e.g. suggestions popped up under the field.

8. Long tasks:
   -  Keep track of the status and subresults in the memory. 

9. Extraction:
    - If your task is to find information - call extract_content on the specific pages to get and store the information.

"""
        text += f"   - use maximum {self.max_actions_per_step} actions per sequence"
        return text

    def input_format(self) -> str:
        return """
INPUT STRUCTURE:
1. Task: The user\'s instructions you need to complete.
2. Hints(Optional): Some hints to help you complete the user\'s instructions.
3. Memory: Important contents are recorded during historical operations for use in subsequent operations.
4. Current URL: The webpage you're currently on
5. Available Tabs: List of open browser tabs
6. Interactive Elements: List in the format:
   [index]<element_type>element_text</element_type>
   - index: Numeric identifier for interaction
   - element_type: HTML element type (button, input, etc.)
   - element_text: Visible text or element description

Example:
[33]<button>Submit Form</button>
[] Non-interactive text


Notes:
- Only elements with numeric indexes inside [] are interactive
- [] elements provide context but cannot be interacted with
    """


class CustomAgentMessagePrompt(AgentMessagePrompt):
    def __init__(
            self,
            state: BrowserState,
            actions: Optional[List[ActionModel]] = None,
            result: Optional[List[ActionResult]] = None,
            include_attributes: list[str] = [],
            step_info: Optional[CustomAgentStepInfo] = None,
    ):
        super(CustomAgentMessagePrompt, self).__init__(state=state,
                                                       result=result,
                                                       include_attributes=include_attributes,
                                                       step_info=step_info
                                                       )
        self.actions = actions

    def get_user_message(self, use_vision: bool = True) -> HumanMessage:
        if self.step_info:
            step_info_description = f'Current step: {self.step_info.step_number}/{self.step_info.max_steps}\n'
        else:
            step_info_description = ''

        time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        step_info_description += f"Current date and time: {time_str}"

        elements_text = self.state.element_tree.clickable_elements_to_string(include_attributes=self.include_attributes)

        has_content_above = (self.state.pixels_above or 0) > 0
        has_content_below = (self.state.pixels_below or 0) > 0

        if elements_text != '':
            if has_content_above:
                elements_text = (
                    f'... {self.state.pixels_above} pixels above - scroll or extract content to see more ...\n{elements_text}'
                )
            else:
                elements_text = f'[Start of page]\n{elements_text}'
            if has_content_below:
                elements_text = (
                    f'{elements_text}\n... {self.state.pixels_below} pixels below - scroll or extract content to see more ...'
                )
            else:
                elements_text = f'{elements_text}\n[End of page]'
        else:
            elements_text = 'empty page'

        state_description = f"""
{step_info_description}
1. Task: {self.step_info.task}. 
2. Hints(Optional): 
{self.step_info.add_infos}
3. Memory: 
{self.step_info.memory}
4. Current url: {self.state.url}
5. Available tabs:
{self.state.tabs}
6. Interactive elements:
{elements_text}
        """

        if self.actions and self.result:
            state_description += "\n **Previous Actions** \n"
            state_description += f'Previous step: {self.step_info.step_number-1}/{self.step_info.max_steps} \n'
            for i, result in enumerate(self.result):
                action = self.actions[i]
                state_description += f"Previous action {i + 1}/{len(self.result)}: {action.model_dump_json(exclude_unset=True)}\n"
                if result.include_in_memory:
                    if result.extracted_content:
                        state_description += f"Result of previous action {i + 1}/{len(self.result)}: {result.extracted_content}\n"
                    if result.error:
                        # only use last 300 characters of error
                        error = result.error.split('\n')[-1]
                        state_description += (
                            f"Error of previous action {i + 1}/{len(self.result)}: ...{error}\n"
                        )

        if self.state.screenshot and use_vision == True:
            # Format message for vision model
            return HumanMessage(
                content=[
                    {'type': 'text', 'text': state_description},
                    {
                        'type': 'image_url',
                        'image_url': {'url': f'data:image/png;base64,{self.state.screenshot}'},
                    },
                ]
            )

        return HumanMessage(content=state_description)
