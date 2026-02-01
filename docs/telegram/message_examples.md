```json
{
  "update_id": 250173215,
  "message": {
    "message_id": 1,
    "from": {
      "id": 7345898170,
      "is_bot": false,
      "first_name": "Emiliano",
      "last_name": "Jankowski",
      "language_code": "en"
    },
    "chat": {
      "id": 7345898170,
      "first_name": "Emiliano",
      "last_name": "Jankowski",
      "type": "private"
    },
    "date": 1769978205,
    "text": "/start",
    "entities": [
      {
        "offset": 0,
        "length": 6,
        "type": "bot_command"
      }
    ]
  }
}
```

```json
{
  "update_id": 250173216,
  "message": {
    "message_id": 2,
    "from": {
      "id": 7345898170,
      "is_bot": false,
      "first_name": "Emiliano",
      "last_name": "Jankowski",
      "language_code": "en"
    },
    "chat": {
      "id": 7345898170,
      "first_name": "Emiliano",
      "last_name": "Jankowski",
      "type": "private"
    },
    "date": 1769978208,
    "text": "hello there!"
  }
}
```

```json
{
  "update_id": 250173217,
  "message": {
    "message_id": 3,
    "from": {
      "id": 7345898170,
      "is_bot": false,
      "first_name": "Emiliano",
      "last_name": "Jankowski",
      "language_code": "en"
    },
    "chat": {
      "id": 7345898170,
      "first_name": "Emiliano",
      "last_name": "Jankowski",
      "type": "private"
    },
    "date": 1769978662,
    "text": "how you doing?"
  }
}
```

## Outbound: send to chat (no reply)

Send a new message to a chat using the `chat.id` as `external_user_id`. Omit `reply_to_message_id` for a standalone message:

```json
{
  "channel": "telegram",
  "external_user_id": "7345898170",
  "text": "Hello!"
}
```

To reply to a specific message, include `reply_to_message_id` (e.g. `"2"` to reply to message_id 2):

```json
{
  "channel": "telegram",
  "external_user_id": "7345898170",
  "text": "Thanks for your message!",
  "reply_to_message_id": "2"
}
```