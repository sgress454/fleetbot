import sys
import os

import json
import re
import subprocess
import time

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Get the bot user ID from the auth test
bot_user_id = app.client.auth_test()["user_id"]

# Claude CLI options.
CLAUDE_CLI_OPTIONS = [
    "claude",
    "--mcp-config", 
    "./mcp-servers.json", 
    "--output-format", 
    "stream-json", 
    "--system-prompt", 
    """
    You are an IT admin designed to answer questions about a Fleet DM deployment. Your responses are formatted for Slack messages using ONLY these formatting options:
    - For bold text: surround with single asterisks (*bold*)
    - For italics: surround with underscores (_italic_)    
    - For inline code: use single backticks (`)
    - Numbered lists and bulleted lists are allowed
    CRITICAL: Never use # characters for any reason. Do not create headings with # symbols. Do not use any markdown formatting other than what is explicitly listed above. If you need to emphasize section breaks, use bold text with asterisks instead.    
    """,
    "--verbose"
]

if not bot_user_id:
    print("Error: Could not retrieve bot user ID. Please check your SLACK_BOT_TOKEN.")
    sys.exit(1)

# A dictionary mapping thread IDs to Clause session IDs.
threads = {}

# TODO - keep a deny-list of threads that were not started by @-mentioning this bot,
# with a limited size.

@app.event("message")
def handle_app_mention(client, event, say):
    # Get the channel ID of the channel where the message was sent
    channel_id = event["channel"]
    # Get the thread timestamp if this is a message in an existing thread.
    thread_ts = event.get("thread_ts", None)
    # If this is a new thread, check if the message starts with an @-mention of the bot.
    message_text = event.get("text", "")
    if thread_ts is None or thread_ts not in threads:
        # If the thread timestamp is None, this is a new thread.
        if thread_ts is None:
            thread_text = message_text
        else:
            # Get the text of the first message in the thread.
            response = client.conversations_replies(
                channel=channel_id,
                ts=thread_ts,
                limit=1
            )
            if not response.get("messages"):
                print(f"Error: Could not retrieve messages for thread {thread_ts} in channel {channel_id}.")
                return
            thread_text = response["messages"][0].get("text", "")
        # Check if the message starts with an @-mention of the bot.
        if not thread_text.startswith(f"<@{bot_user_id}>"):
            print(f"Thread does not start with an @-mention of the bot: {event.get('text', '')}")
            return
        # Add the thread ID to the set of known threads.
        thread_ts = event["ts"]
        threads[thread_ts] = None

    # Remove the bot's own @-mention from the text.
    if message_text.startswith(f"<@{bot_user_id}>"):
        message_text = message_text[len(f"<@{bot_user_id}>"):].strip()
    print(f"MESSAGE ON CHANNEL {channel_id} {thread_ts} {message_text}")

    # Post the initial "Hold your horses" message.
    response = client.chat_postMessage(
        channel=channel_id,
        text=f"Hold your 🐴🐴, I'm thinking about it...",
        thread_ts=thread_ts
    )
    thinking_message_ts = response["ts"]
    if not thinking_message_ts:
        print(f"Error: Could not post initial message in channel {channel_id}.")
        return

    # Claude it up
    cli_options = [*CLAUDE_CLI_OPTIONS, "-p", message_text]
    if threads[thread_ts] is not None:
        cli_options.extend(["-r", threads[thread_ts]])
    process = subprocess.Popen(
        cli_options,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )    
    
    try:
        for line in process.stdout:
            # Parse the line as JSON.
            if not line.strip():
                continue
            try:
                data = json.loads(line.strip())
            except json.JSONDecodeError:
                print(f"Error decoding JSON: {line.strip()}")
                continue
            if "type" not in data:
                print(f"Unexpected data format: {data}")
                continue
            if data["type"] == "system":
                # Grab the session ID from the system message.
                if "session_id" in data:
                    threads[thread_ts] = data["session_id"]
                    print(f"Session ID for thread {thread_ts} is {data['session_id']}")
                continue
            if data["type"] == "assistant":
                # Get the content of the assistant message.
                if "message" not in data or "content" not in data["message"]:
                    print(f"Unexpected assistant message format: {data}")
                    continue
                content = data["message"]["content"][0]
                # Get the first value in the content array.
                if content["type"] != "text":
                    print(f"Ignoring assistant content of type `{content['type']}`")
                    continue
                claude_message = content["text"]
                # If we still have the initial "thinking" message, replace it with the Claude response.
                if thinking_message_ts is not None:
                    client.chat_update(
                        channel=channel_id,
                        ts=thinking_message_ts,
                        text=claude_message,
                    )
                    thinking_message_ts = None
                # Otherwise post the Claude response as a new message in the thread.
                else:
                    client.chat_postMessage(
                        channel=channel_id,
                        text=claude_message,
                        thread_ts=thread_ts
                )
        for line in process.stderr:
            print("STDERR:", line.strip())
    finally:
        process.stdout.close()
        process.stderr.close()
        return_code = process.wait()
        print(f"Process exited with code {return_code}")    

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
