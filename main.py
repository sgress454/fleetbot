import sys
import os

import json
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

# Initializes your app with your bot token and socket mode handler
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

trigger = r"simply (\w+) (.*)[!.?]?$"

# Get the bot user ID from the auth test
bot_user_id = app.client.auth_test()["user_id"]

if not bot_user_id:
    print("Error: Could not retrieve bot user ID. Please check your SLACK_BOT_TOKEN.")
    sys.exit(1)

# The set of threads we know were started by @-mentioning this bot.
thread_ids = set()
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
    if thread_ts is None or thread_ts not in thread_ids:
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
        thread_ids.add(thread_ts)

    # Remove the bot's own @-mention from the text.
    if message_text.startswith(f"<@{bot_user_id}>"):
        message_text = message_text[len(f"<@{bot_user_id}>"):].strip()
    print(f"MESSAGE ON CHANNEL {channel_id} {thread_ts} {message_text}")

    client.chat_postMessage(
        channel=channel_id,
        text=f"You said: '{message_text}'",
        thread_ts=thread_ts
    )

# Start your app
if __name__ == "__main__":
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
