# FleetBot 🙌🤖🥳

A hyper-intelligent yet modest and down-to-earth robot that answers all of your burning Fleet questions.

## Prerequisites

* Python 3.8+
* Node.js 18+
* A system that uses `systemd` (most Linux systems) if you want to install as a service.
* [Claude CLI](https://docs.anthropic.com/en/docs/claude-code/setup)
* The Fleet MCP server running locally.

## To set up

1. Create an .env file containing `SLACK_BOT_TOKEN` and `SLACK_APP_TOKEN` keys
2. Either log in to Claude CLI using an Anthropic account (for example with Claude Pro) _or_ add an `ANTHROPIC_API_KEY` key to `.env` as well.
3. Run `./setup.sh` to set up the bot's environment.

# To install Fleetbot as a service

Run `./install.sh`