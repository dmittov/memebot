import logging
from datetime import datetime, timedelta, timezone
from functools import cache, cached_property
from io import BytesIO

import vertexai
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from telegram import Bot, Message
from vertexai.generative_models import GenerationConfig, GenerativeModel, Image, Part

from memebot.config import MODEL_NAME, get_token

logger = logging.getLogger(__name__)


class Explainer:
    # TODO: fix race condition
    # TODO: check allows another request in 24hrs

    def __init__(self, model_name: str) -> None:
        self.n_generations_limit = 10
        self.n_hour_limit = 24
        self.model = GenerativeModel(
            model_name=model_name,
            system_instruction=(
                "Дай перевод мема на русский язык."
                " Если язык оригинала немецкий, объясни сложные моменты грамматики"
                ", только те что может не знать"
                " человек с уровнем владения языка B1."
                " Не объясняй грамматику уровня B1 и ниже."
                " Объясни мем. Является ли он смешным?"
                " Какую ты ему поставишь оценку по шкале от 1 до 10?"
            ),
            generation_config=GenerationConfig(
                max_output_tokens=1000, temperature=0.0, candidate_count=1
            ),
        )

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

    async def get_image(self, message: Message) -> Image:
        assert message.reply_to_message is not None
        file_record = max(
            (
                photo
                for photo in message.reply_to_message.photo
                if ( photo.width < 800 and photo.height < 800 )
            ),
            key=lambda photo: photo.width,
        )
        hfile = await Bot(token=get_token()).get_file(file_record.file_id)
        buffer = BytesIO()
        await hfile.download_to_memory(out=buffer)
        buffer.seek(0)
        return Image.from_bytes(buffer.read())

    async def explain(self, message: Message) -> None:
        logger.info("Running explain")
        if not (await self.__check(message=message)):
            return
        image = await self.get_image(message=message)
        logger.info("Downloaded image: %d", len(image.data))
        assert message.reply_to_message is not None
        caption = (
            "Meme: "
            if not message.reply_to_message.caption
            else message.reply_to_message.caption
        )
        response = self.model.generate_content(
            contents=[
                Part.from_text(caption),
                Part.from_image(image),
            ],
        )
        # TODO: handle
        # response.candidates[0].finish_reason
        # TODO: parts > 0
        if len(response.candidates[0].content.parts) > 1:
            logger.warning(
                "Found more than 1 [%d] part",
                len(response.candidates[0].content.parts),
            )
        explanation = response.candidates[0].content.parts[0].text
        logger.info(explanation)
        logger.info("Going to send to %d", message.chat.id)
        await Bot(token=get_token()).send_message(
            chat_id=message.chat.id, reply_to_message_id=message.id, text=explanation
        )
        self.__register(message=message)


@cache
def get_explainer() -> Explainer:
    vertexai.init()
    return Explainer(model_name=MODEL_NAME)
