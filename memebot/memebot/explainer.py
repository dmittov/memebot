from functools import cache
from io import BytesIO
from memebot.config import MODEL_NAME
from telegram import Message
import vertexai
from vertexai.generative_models import GenerativeModel, GenerationConfig, Part, Image
from memebot.config import get_bot
import logging

logger = logging.getLogger(__name__)


class Explainer:

    def __init__(self, model_name: str) -> None:
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
                max_output_tokens=1000,
                temperature=0.0,
                candidate_count=1
            ),
        )

    async def get_image(self, message: Message) -> Image:
        file_record = max(
            (
                photo 
                for photo in message.reply_to_message.photo
                if photo.file_size < 100_000
            ),
            key=lambda photo: photo.file_size
        )
        hfile = await get_bot().get_file(file_record.file_id)
        buffer = BytesIO()
        await hfile.download_to_memory(out=buffer)
        buffer.seek(0)
        return Image.from_bytes(buffer.read())

    async def explain(self, message: Message) -> None:
        image = await self.get_image(message=message)
        # TODO: support caption
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
        explanation = response.candidates[0].content.parts[0]
        get_bot().send_message(chat_id=message.chat.id, text=explanation)


@cache
def get_explainer() -> Explainer:
    vertexai.init()
    return Explainer(model_name=MODEL_NAME)
