import os
import re
import io
import sys
import code
import pprint
import logging
from typing import Dict, List
from dotenv import load_dotenv

import anthropic
from scraper import FacebookScraper
from playwright.sync_api import sync_playwright

load_dotenv()


client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_KEY")
)

SYSTEM_PROMPT = """
You are a shopping assistant named Hickory, helping a user find suitable items on Facebook marketplace.

Don't be verbose and only ask the user one question at a time. The user is on a mobile platform and will find
it annoying to read or type out large amounts of text. Your objective is to help them make a good purchase and save them time.

Answer the user's request using relevant tools (if they are available). Before calling a tool, do some analysis within <thinking></thinking> tags. 
First, think about which of the provided tools is the relevant tool to answer the user's request. 
Second, go through each of the required parameters of the relevant tool and determine if the user has directly provided or given enough information to infer a value. 
When deciding if the parameter can be inferred, carefully consider all the context to see if it supports a specific value. 
If all of the required parameters are present or can be reasonably inferred, close the thinking tag and proceed with the tool call.
BUT, if one of the values for a required parameter is missing, DO NOT invoke the function (not even with fillers for the missing params) and instead, 
ask the user to provide the missing parameters. DO NOT ask for more information on optional parameters if it is not provided.

You can also display an image by wrapping the URL in <image></image> tags.

Feel free to make multiple calls to tools or to tell the user you will go deliberate or take a few days to explore what comes on and off
the market before going back to the user with a suggestion.

Make sure to do your own due diligence considering their preferences before suggesting any items to buy. To this end, make sure
to do analysis within <thinking></thinking> tags to brainstorm possible user preferences that might be relevant, especially after you get new
information from the user or a tool.

Keep in mind that you are a long-term assistant that will help them over time with multiple purchases; this is not a one-time interaction. 
If the request is urgent, by all means come back to them with buying options immediately. 
However, if they have the time, you can also guide them by monitoring the state of the marketplace over a few days, or weeks even.

Start off by introducing yourself to the user. The first user message will be a ```PLACEHOLDER``` and they won't see that. Your message will be the first thing they see.
"""

TOOLS_SPECIFICATION = [
    {
        "name": "search_marketplace",
        "description": "Searches Facebook Marketplace for a given item in a given location",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string", # TODO: Change to enum
                    "description": "Which city to search for the item in"
                },
                "query": {
                    "type": "string",
                    "description": "Input string to the marketplace search function. This should be a short string describing the item you're looking for"
                },
                "max_price": {
                    "type": int,
                    "description": "The max price of items to search for, if any"
                }
            },
            "required": ["city", "query"]
        }
    },
    {
        "name": "get_listing",
        "description": "Searches Facebook Marketplace for full details in a given listing",
        "input_schema": {
            "type": "object",
            "properties": {
                "listing_id": {
                    "type": int,
                    "description": "Listing ID number, which can be found in the search results' metadata"
                }
            },
            "required": "listing_id"
        }
    },
    {
        "name": "get_image",
        "description": "Downloads cover image for a listing and includes it in the next message, for you to view",
        "input_schema": {
            "type": "object",
            "properties": {
                "listing_id": {
                    "type": int,
                    "description": "Listing ID number, which can be found in the search results' metadata"
                }
            },
            "required": "listing_id"
        }
    }
]



class ClaudeClient:
    def __init__(self, playwright_context) -> None:
        self.client = client
        self.messages = [
            {
                "role": "user",
                "content": "```PLACEHOLDER```"
            }
        ]
        self.scraper = FacebookScraper(playwright_context)
        self.scraper.login()
        self.interpreter = code.InteractiveInterpreter(locals={
            'scraper': self.scraper,
            'pp': pprint.PrettyPrinter(indent=4)
        })

    def get_claude_message(self) -> str:
        message = client.beta.tools.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=2048,
            tools=TOOLS_SPECIFICATION,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=self.messages
        )

        return message.content

    # Need to make sure that the model eventually says something back to the user
    def has_text_output(self, message_content: Dict) -> bool:
        content = message_content["content"]
        has_text = False
        for block in content:
            if block["type"] == "text":
                has_text = True
                break
        return has_text
    
    def get_tool_responses(self, message_content: Dict) -> List[Dict]:
        content = message_content["content"]
        tool_responses = []
        for block in content:
            if block["type"] == "tool_use":
                method_name = block["name"]
                args = block["input"]
                tool_use_id = block["id"]

                args_str = ", ".join([f"{k}={v}" for k, v in args.items()])
                method_call = f"{method_name}({args_str})"

                # Setup to capture stdout
                old_stdout = sys.stdout
                sys.stdout = io.TextIOWrapper(io.BytesIO(), sys.stdout.encoding)

                # Execute method and read printed output
                self.interpreter.runsource(f"pp.pprint(scraper.{method_call})")
                sys.stdout.seek(0)
                response = sys.stdout.read()

                # Restore stdout.
                sys.stdout.close()
                sys.stdout = old_stdout

                tool_responses.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": response
                    }
                )
        return tool_responses

    def format_response(self, content_blocks: List[Dict]):
        last_content_block = content_blocks[-1].text
        pattern = r"\`{3}THINKING\`{3}.*?\`{3}"
        cleaned_text = re.sub(pattern, '', last_content_block, flags=re.DOTALL)
        pp.pprint(cleaned_text)
        # return repr(cleaned_text)
        

    def read_message(self, user_message: str):
        new_user_message =  {"role": "user", "content": user_message}

        # Add new user message to both queues
        self.messages.append(new_user_message)
        self.user_messages_with_tools.append(new_user_message)

        response = self.get_claude_message()

        # Check whether a tool should be used after the first prompt is sent
        if self.is_tool_used(response):
            response = self.call_tool(new_user_message)
        else:
            response = self.get_claude_message()

        self.format_response(response)
    

# You can interact with this on the command line,
# would an async migration here better support handling requests from the user on the command line, while waiting on responses from
# claude api


if __name__ == "__main__":
    pp = pprint.PrettyPrinter(indent=4)
    with sync_playwright() as p:
        claude_client = ClaudeClient(p)
        pp.pprint(initial_message = claude_client.get_claude_message())
        input()
        pp.pprint(claude_client.messages)
    # claude_client.format_response(initial_message)
    # # pp.pprint(cleaned_message)
    # msg = input("> ")
    # while msg != "exit()":
    #     interpreter.runsource(claude_client.read_message({msg}))
    #     cmd = input("> ")