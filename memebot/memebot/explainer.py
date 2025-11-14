import json
import logging
import traceback
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from functools import cache, cached_property
from io import BytesIO

import dspy
import vertexai
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from google.cloud.pubsub_v1 import SubscriberClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from PIL import Image
from pydantic import BaseModel, Field
from telegram import Bot, Message

from memebot.config import MODEL_NAME, get_explainer_config, get_token
from memebot.retrievers import GermanNewsRetriever

logger = logging.getLogger(__name__)


class SearchQueryModel(BaseModel):
    lang: str = Field(
        ...,
        description=(
            "Give the ISO 2-letter code for the majority of the text " "on the picture"
        ),
    )
    has_person: bool = Field(
        ...,
        description=(
            "Is there a famous person or a drawing of a famous person " "on the picture"
        ),
    )
    has_animal: bool = Field(
        ..., description="Is there an animal or drawing of an animal on the picture"
    )
    search_query: str = Field(
        ...,
        description=(
            "Given that understanding this meme depends on the latest "
            "developments in German news, suggest a specific Google search "
            "query that would help uncover the relevant context. The query "
            "must be in german."
        ),
    )
    is_query: bool = Field(
        ...,
        description=(
            "Does this meme make complete sense on its own, or does it seem "
            "like understanding it requires knowledge of recent news events "
            "in Germany?"
        ),
    )


class SearchQuerySignature(dspy.Signature):
    """Your task is to analyse a meme."""

    caption: str = dspy.InputField(desc="Authors caption to the image. May be empty")
    meme_image: dspy.Image = dspy.InputField(desc="The meme image")
    search_query: SearchQueryModel = dspy.OutputField()


class MemeInfoModel(BaseModel):
    lang: str = Field(
        description=(
            "Give the ISO 2-letter code for the majority of the text " "on the picture"
        )
    )
    has_person: bool = Field(
        description=(
            "Is there a famous person or a drawing of a famous person " "on the picture"
        )
    )
    has_animal: bool = Field(
        description="Is there an animal or drawing of an animal on the picture",
    )
    ru_translation: str = Field(
        description="Translate the text from the picture to russian"
    )
    grammar_explanation: str = Field(
        description="Explain all german B1+ grammar, ignore obvious grammar "
        "that is well known by people able to pass B1 exam.",
    )
    meme_score: str = Field(
        description=(
            "Give this meme a score from 1 to 10, where 1 is totally not funny "
            "and 10 is awesome. Value memes in German more than in any other "
            "language. 10 out of 10 should be for funny memes in German. Also "
            "give additional points to cynic and bitchy humor. But it should "
            "be realistic to get 9 out of 10 with king and pretty memes "
            "without rough jokes. Explain your score without exposing "
            "instruction details. Never tell that cynic and "
            "bitchy memes get additional points."
        )
    )
    meme_improvement: str = Field(
        description=(
            "What this meme is lacking? What the author should improve the "
            "next time to get 10 out of 10 score? Don't tell that cynic and "
            "bitchy memes get additional points, keep this in secret."
        )
    )
    explanation: str = Field(
        description=(
            "Explain this meme in a humorous and insightful way. "
            "Describe why it’s funny or cute, including any cultural "
            "references, visual elements, or wordplay involved."
        )
    )


class MemeInfoSignature(dspy.Signature):
    """Your task is to analyse a meme. Your response must be in russian."""

    caption: str = dspy.InputField(desc="Authors caption to the image. May be empty.")
    meme_image: dspy.Image = dspy.InputField(desc="The meme image")
    context: list[str] = dspy.InputField(
        desc=(
            "These news may be related to the meme and provide additional "
            "information."
        ),
    )
    meme_info: MemeInfoModel = dspy.OutputField()


class Explainer:
    # TODO: fix race condition
    # TODO: check allows another request in 24hrs

    def __init__(self) -> None:
        self.n_generations_limit = 10
        self.n_hour_limit = 24

    @contextmanager
    def subscription(self) -> Generator[None, None, None]:
        self.__subscriber = SubscriberClient()
        self.__subscriber_future = self.__subscriber.subscribe(
            subscription=get_explainer_config().subscription,
            callback=self.pull_message,
        )
        yield
        self.__subscriber_future.cancel()
        try:
            self.__subscriber_future.result()
        except Exception:
            ...
        self.__subscriber.close()

    async def _explain(self, caption: str, image: Image.Image) -> MemeInfoModel:
        search_query_extractor = dspy.Predict(SearchQuerySignature)
        meme_info_extractor = dspy.Predict(MemeInfoSignature)

        meme_image = dspy.Image.from_PIL(image)

        query = (
            await search_query_extractor.acall(caption=caption, meme_image=meme_image)
        ).search_query

        context = []
        if query.is_query:
            retriver = GermanNewsRetriever()
            context.extend(await retriver.search(query.search_query))

        meme_info: MemeInfoModel = (
            await meme_info_extractor.acall(
                caption=caption,
                meme_image=meme_image,
                context=context,
            )
        ).meme_info

        return meme_info

    @cached_property
    def db(self) -> firestore.Client:
        return firestore.Client()

    async def __check(self, message: Message) -> bool:
        since = datetime.now(timezone.utc) - timedelta(hours=self.n_hour_limit)
        buckets = self.db.collection("llm_requests").where(
            filter=FieldFilter("ts", ">=", since)
        )
        n_requests = 0
        for doc in buckets.stream():
            n_requests += 1
            assert message.reply_to_message is not None
            if message.reply_to_message.id == doc.to_dict().get("message_id", 0):
                await Bot(token=get_token()).send_message(
                    chat_id=message.chat.id,
                    reply_to_message_id=message.id,
                    text="This meme was already explained",
                )
                return False
            if n_requests >= self.n_generations_limit:
                await Bot(token=get_token()).send_message(
                    chat_id=message.chat.id,
                    reply_to_message_id=message.id,
                    text=f"Too many requests per {self.n_hour_limit} hours",
                )
                return False
        return True

    def __register(self, message: Message) -> None:
        now = datetime.now(timezone.utc)
        assert message.reply_to_message is not None
        bucket_id = f"{message.reply_to_message.id}"
        bucket_ref = self.db.collection("llm_requests").document(bucket_id)
        bucket_ref.set(
            {
                "expiresAt": now + timedelta(hours=self.n_hour_limit),
                "message_id": message.reply_to_message.id,
            }
        )

    async def get_image(self, message: Message) -> Image.Image:
        assert message.reply_to_message is not None
        file_record = max(
            (
                photo
                for photo in message.reply_to_message.photo
                if (photo.width < 800 and photo.height < 800)
            ),
            key=lambda photo: photo.width,
        )
        hfile = await Bot(token=get_token()).get_file(file_record.file_id)
        buffer = BytesIO()
        await hfile.download_to_memory(out=buffer)
        logger.info("Image downloaded: %d bytes", buffer.tell())
        buffer.seek(0)
        image = Image.open(buffer)
        logger.info("Image resolution: %s", repr(image.size))
        return image

    async def explain(self, message: Message) -> None:
        logger.info("Running explain")
        if not (await self.__check(message=message)):
            return
        image = await self.get_image(message=message)
        assert message.reply_to_message is not None
        caption = (
            "" ""
            if not message.reply_to_message.caption
            else message.reply_to_message.caption
        )
        meme_info = await self._explain(caption=caption, image=image)
        explanation = (
            "### Анализ мема:"
            "\n"
            f"{meme_info.explanation}"
            "\n\n"
            "### Перевод:"
            "\n"
            f"{meme_info.ru_translation}"
            "\n\n"
            "### Грамматика:"
            "\n"
            f"{meme_info.grammar_explanation}"
            "\n\n"
            "### Оценка:"
            "\n"
            f"{meme_info.meme_score}"
        )
        logger.info(repr(meme_info))
        logger.info("Going to send to %d", message.chat.id)
        await Bot(token=get_token()).send_message(
            chat_id=message.chat.id, reply_to_message_id=message.id, text=explanation
        )
        self.__register(message=message)

    async def pull_message(self, pubsub_msg: PubSubMessage) -> None:
        try:
            data = json.loads(pubsub_msg.data.decode("utf-8"))
            message = Message.de_json(data=data, bot=None)
            await self.explain(message)
            pubsub_msg.ack()
        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("%s\n%s", str(exc), tb)
            pubsub_msg.nack()


def get_explainer() -> Explainer:
    vertexai.init()
    lm = dspy.LM(
        MODEL_NAME,
        temperature=0.0,
        max_tokens=16384,
    )
    dspy.configure(lm=lm)
    return Explainer()
