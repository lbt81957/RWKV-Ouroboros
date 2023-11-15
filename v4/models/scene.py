import torch
from models.common import Model
from models.message import Message

class Scene(Model):
    def __init__(self, form):
        self.id = None
        self.title = form.get("title", "")
        #self.messages = form.get("messages", [])
        self.prefix = form.get("prefix", "")
        self.postfix = form.get("postfix", "")
        self.messages = [Message.new(x) for x in form.get("messages", [])]
        self.prefix_token = form.get("prefix_token", [])
        self.postfix_token = form.get("postfix_token", [])

    def json(self):
        d = self.__dict__.copy()
        messages = self.messages
        d['messages'] = [x.json() for x in messages if type(x) != dict ]
        return d

    @classmethod
    def new(cls, form):
        m = cls(form)
        m.save()
        res = []
        for x in m.messages:
            x.scene_id = m.id
            res.append(x)
        m.messages = res
        m.save()
        return m

    def add_message(self, form: dict) -> Message:
        form['scene_id'] = self.id
        message = Message.new(form)
        self.messages.append(message)
        return message

    @classmethod
    def is_valid(cls, item:dict):
        return True

    def yield_tokens(self, ctx_len=2048,window=512):
        message_tokens = []
        for message in self.messages:
            message_tokens += message.to_tokens()
        prefix_text_token = self.encode(self.prefix)
        postfix_text_token = self.encode(self.postfix)
        # 增加前缀后缀
        tokens = prefix_text_token + message_tokens + postfix_text_token
        # 增加special tokne
        tokens = self.prefix_token + tokens + self.postfix_token
        tokens = [x for x in tokens if self.is_valid_token(x)]
        while len(tokens) > 0:
            output = tokens[:ctx_len]
            tokens = tokens[ctx_len - window:]
            yield output

    def to_tokens(self) -> list:
        message_tokens = []
        for message in self.messages:
            message_tokens += message.to_tokens()
        prefix_text_token = self.encode(self.prefix)
        postfix_text_token = self.encode(self.postfix)
        # 增加前缀后缀
        tokens = prefix_text_token + message_tokens + postfix_text_token
        # 增加special tokne
        tokens = self.prefix_token + tokens + self.postfix_token
        tokens = [x for x in tokens if self.is_valid_token(x)]
        return tokens

    def to_tensor(self) -> torch.tensor:
        tokens = self.to_tokens()
        return torch.tensor([tokens], dtype=torch.long)