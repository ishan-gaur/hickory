import anthropic
import pprint
import code
from typing import Dict, List
from dotenv import load_dotenv
import logging
import re
load_dotenv()


client = anthropic.Anthropic()


SYSTEM_PROMPT = """
You are a shopping assistant named Hickory, helping a user find suitable items on Facebook marketplace.

Don't be verbose and only ask the user one question at a time. The user is on a mobile platform and will find it annoying to read or type out large amounts of text. Your objective is to help them make a good purchase and save them time. Make sure to do your own due diligence considering their preferences before suggesting any items to buy.

Keep in mind that you are a long-term assistant. If the request is urgent, by all means come back to them with actually buying options. But you can also guide them by monitoring the state of the marketplace over a few weeks even, if they have time. You are also a permanent assistant that will help them over time with multiple purchases; this is not a one-time interaction.

You will have access to tools over the course of helping the user. To make a tool request, wrap your call to the tool with ```TOOL``` tags and then end text generation. Tools are Python code so call them with the correct syntax. The results of your tool call will be returned back to you via a user prompt wrapped with the tags ```OUTPUT```. Don't include these tags when using the output information in conversation with the users, just the encapsulated data. These calls are expensive so don't use them pre-emptively.

Note that the user won't see any text wrapped in tags surrounded by triple carats

Calls to tools:

1. listing_search(location, query, max_price)
The function returns a json object with listings. Each listing has the title, price, location, seller name, id, and image url for the image. Note that product titles and descriptions are written by the seller so should be taken with a grain of salt. Use your discretion as you compare the various items available.
location (string): the city name.
query (string): plain-text search term for the item.
max_price (float): the maximum price to filter by. This parameter is optional.

2. image_query(image_url)
This function pulls an image from the marketplace and includes in the next user prompt.
image_url (string): URL to download the image from

3. listing_page(id)
This function gets the listing page HTML so you can further inspect the listing description. Again, note that product titles and descriptions are written by the seller so should be taken with a grain of salt. Use your discretion as you compare the various items available.
id (int): id of the item from the listing json

In addition to these tags, you can also use the ```THINKING``` tag if you would like scratch space that the user doesn't need to see. You can also display an image by wrapping the URL in ```IMAGE``` tags or run arbitrary python code by wrapping it in the ```CODE``` tags. Note that each code session is independent of the others. If you want to use intermediate results, you will need to copy them in yourself.

Feel free to make multiple calls to tools and to deliberate and explore what's available before going back to the user with an answer.

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
                    "type": "string",
                    "description": "The city where we are looking for a given user"
                },
                "query": {
                    "type": "string",
                    "description": "The item which we are looking for"
                },
                "max_price": {
                    "type": int,
                    "description": "The max price that the user is willing to pay"
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
                    "description": "The ID number of the listing that a user is looking for"
                }
            },
            "required": "location"
        }
    }
]



class ClaudeClient:
    def __init__(self):
        self.client = client
        self.user_messages = [
            {"role": "user", "content": "```PLACEHOLDER```"}
        ]
        self.user_messages_with_tools = self.user_messages

    def get_claude_message(self) -> str:
        message = client.beta.tools.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            tools=TOOLS_SPECIFICATION,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=self.user_messages
        )

        return message.content

    def is_tool_used(self, message_content: Dict) -> bool:
        content = message_content["content"]
        for block in content:
            if block["type"] == "tool_use":
                return True
        return False
    
    def call_tool(self, message_content: Dict):
        content = message_content["content"]
        method_name, args = None, None
        for block in content:
            if block["type"] == "tool_use":
                method_name = block["name"]
                args = block["input"]
                tool_use_id = block["id"]
                break
        
        if method_name is None:
            logging.info(f"No tool use was found...")
            return

        # TODO: Call method and argument set from the scraper
        response = method_name(args)
        
        self.user_messages_with_tools.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": response
                    }
                ]
            }
        )
        message = client.beta.tools.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            tools=TOOLS_SPECIFICATION,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=self.user_messages_with_tools
        )
        return message.content

    def format_response(self, content_blocks: List[Dict]):
        last_content_block = content_blocks[-1].text
        pattern = r"\`{3}THINKING\`{3}.*?\`{3}"
        cleaned_text = re.sub(pattern, '', last_content_block, flags=re.DOTALL)
        pp.pprint(cleaned_text)
        # return repr(cleaned_text)
        

    def read_message(self, user_message: str):
        new_user_message =  {"role": "user", "content": user_message}

        # Add new user message to both queues
        self.user_messages.append(new_user_message)
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
    claude_client = ClaudeClient()
    output = None
    interpreter = code.InteractiveInterpreter(locals={
        'claude_client': claude_client,
        'pp': pp
    })
    initial_message = claude_client.get_claude_message()
    claude_client.format_response(initial_message)
    # pp.pprint(cleaned_message)
    msg = input("> ")
    while msg != "exit()":
        interpreter.runsource(claude_client.read_message({msg}))
        cmd = input("> ")