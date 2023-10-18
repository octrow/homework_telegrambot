### Telegram-bot

This is a telegram-bot for checking the status of your homework on Yandex.Practicum.
It sends you messages when the status changes - taken for review, has comments, accepted.

### Technologies:
- Python 3.9
- python-dotenv 0.19.0
- python-telegram-bot 13.7

### How to run the project:

Clone the repository and go to it in the command line:

```
git clone git@github.com:octrow/homework_telegrambot.git
```

```
cd homework_telegrambot
```

Create and activate a virtual environment:

```
python -m venv env
```

```
source env/bin/activate
```

Install the dependencies from the requirements.txt file:

```
python -m pip install --upgrade pip
```

```
pip install -r requirements.txt
```

Write the necessary keys in the environment variables (file .env):
- token of your profile on Yandex.Practicum
- token of your telegram-bot
- ID in telegram


Run the project:

```
python homework.py
```
