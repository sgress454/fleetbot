import sys
import os

import json
import random
import subprocess

from dotenv import load_dotenv

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# Get the bot user ID from the auth test
bot_user_id = app.client.auth_test()["user_id"]

# Read the system prompt from file
def read_system_prompt():
    try:
        with open("system-prompt.txt", "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        print("Warning: system-prompt.txt not found, using default prompt", flush=True)
        return "You are an IT admin designed to answer questions about a Fleet DM deployment."

# Claude CLI options.
CLAUDE_CLI_OPTIONS = [
    "claude",
    "--mcp-config", 
    "./mcp-servers.json", 
    "--output-format", 
    "stream-json", 
    "--system-prompt", 
    read_system_prompt(),
    "--verbose"
]

THINKING_MESSAGES = [
    "Hold your 🐴🐴, I'm thinking about it...",
    "Just a moment, I'm working on it...",
    "Give me a second, I'm on it...",
    "Hang tight, I'm processing your request...",
    "Let me think about that for a moment...",
    "Processing your request, please hold on...",
    "Consulting the office :cat: for advice…",
    "Telling my :turtle: CPU to hurry up...",
    "Pausing to pet the :dog2:... almost there!",
    "Looking for the missing :bone: of knowledge...",
]

if not bot_user_id:
    print("Error: Could not retrieve bot user ID. Please check your SLACK_BOT_TOKEN.", flush=True)
    sys.exit(1)

# A dictionary mapping thread IDs to Clause session IDs.
allowed_threads = {}
denied_threads = {}

# TODO - keep a deny-list of threads that were not started by @-mentioning this bot,
# with a limited size.

@app.event("message")
def handle_message(client, event, say):
    # Get the channel ID of the channel where the message was sent
    channel_id = event["channel"]
    # Get the thread timestamp if this is a message in an existing thread.
    thread_ts = event.get("thread_ts", None)
    # If this is a new thread, check if the message starts with an @-mention of the bot.
    message_text = event.get("text", "")

    # If this is a message @-mentioning the bot, remove the mention from the text.
    if message_text.startswith(f"<@{bot_user_id}>"):
        message_text = message_text[len(f"<@{bot_user_id}>"):].strip()
    else:
    # Otherwise ignore the message.
        return

    # The allow/deny lists are intended to allow the bot to respond to messages
    # that are not directly @-mentioning it. Turning off this functionality for
    # now in favor of only responding to @-mentions, but leaving the code here for reference.
    #
    # If this is a new thread or a thread on the deny-list, 
    # and the message is not an @-mention of the bot,
    # put it in the deny list.
    # if (thread_ts is None or thread_ts in denied_threads) and not is_mention:
    #     denied_threads[thread_ts or event["ts"]] = {}
    #     return

    # If this is an existing thread that's not on the allow-list,
    # scan all messages in the thread to see if there's an @-mention of the bot.
    conversation_context = []
    if thread_ts is None:
        allowed_threads[event["ts"]] = {
            "posted_initial_message": False,
            "session_id": None
        }
        thread_ts = event["ts"]
    elif thread_ts not in allowed_threads:
        # Get all messages in the thread.
        response = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts
        )
        if not response.get("messages"):
            print(f"Error: Could not retrieve messages for thread {thread_ts} in channel {channel_id}.", flush=True)
            return
        # Check if any message in the thread starts with an @-mention of the bot.
        convo_has_mention = False
        for message in response["messages"]:
            convo_msg_text = message.get("text", "")
            if not convo_msg_text:
                continue
            convo_msg = {
                "text": convo_msg_text
            }
            if message.get("user") == bot_user_id:
                convo_msg["speaker"] = "assistant"
                convo_has_mention = True
            else:
                convo_msg["speaker"] = "user"
                if message.get("text", "").startswith(f"<@{bot_user_id}>"):
                    convo_has_mention = True
            conversation_context.append(convo_msg)
        if convo_has_mention:
            allowed_threads[thread_ts] = {
                "posted_initial_message": thread_ts is not None,
                "session_id": None
            }
            if thread_ts in denied_threads:
                del denied_threads[thread_ts]
        else:
            denied_threads[thread_ts] = {}
            return
        
    print(f"MESSAGE ON CHANNEL {channel_id} {thread_ts} {message_text}", flush=True)
    if allowed_threads[thread_ts]["session_id"] is not None:
        print(f"CONTINUING WITH SESSION: {allowed_threads[thread_ts]['session_id']}", flush=True)
    elif len(conversation_context) > 0:
        print("JOINING PREVIOUS CONVERSATION FOR THREAD", flush=True)
    else:
        print("STARTING NEW CONVERSATION FOR THREAD", flush=True)

    # If we have no session ID for this thread, post an initial "thinking" message.
    # Otherwise, post a simpler "thinking" message.
    thinking_message = THINKING_MESSAGES[random.randint(0, len(THINKING_MESSAGES) - 1)] if allowed_threads[thread_ts]["posted_initial_message"] is False else "🤔 Thinking..."
    allowed_threads[thread_ts]["posted_initial_message"] = True
    response = client.chat_postMessage(
        channel=channel_id,
        text=thinking_message,
        thread_ts=thread_ts
    )
    thinking_message_ts = response["ts"]
    if not thinking_message_ts:
        print(f"Error: Could not post initial message in channel {channel_id}.", flush=True)
        return

    # Claude it up
    claude_message = message_text
    if len(conversation_context) > 0:
        claude_message = f"""
        You are continuing a conversation with the user. Here is the context:
        {json.dumps(conversation_context, indent=2)}
        
        The user just said:
        {message_text}
        """
    cli_options = [*CLAUDE_CLI_OPTIONS, "-p", claude_message]
    if allowed_threads[thread_ts]["session_id"] is not None:
        cli_options.extend(["-r", allowed_threads[thread_ts]["session_id"]])
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
                print("CLAUDE:", line.strip(), flush=True)
                data = json.loads(line.strip())
            except json.JSONDecodeError:
                print(f"Error decoding JSON: {line.strip()}", flush=True)
                continue
            if "type" not in data:
                print(f"Unexpected data format: {data}", flush=True)
                continue
            if data["type"] == "system":
                # Grab the session ID from the system message.
                if "session_id" in data:
                    allowed_threads[thread_ts]["session_id"] = data["session_id"]
                    print(f"Session ID for thread {thread_ts} is {data['session_id']}", flush=True)
                continue
            if data["type"] == "assistant":
                # Get the content of the assistant message.
                if "message" not in data or "content" not in data["message"]:
                    print(f"Unexpected assistant message format: {data}", flush=True)
                    continue
                content = data["message"]["content"][0]
                # Get the first value in the content array.
                if content["type"] != "text":
                    print(f"Ignoring assistant content of type `{content['type']}`", flush=True)
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
            print("STDERR:", line.strip(), flush=True)
    finally:
        process.stdout.close()
        process.stderr.close()
        return_code = process.wait()
        print(f"Claude process exited with code {return_code}", flush=True)

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
