from io import BytesIO
from telegram import Bot
import vertexai
import pytest
from PIL import Image

from memebot.config import get_token
from memebot.explainer import Explainer


class TestExplainer:

    @pytest.mark.asyncio
    async def test_image(self) -> None:
        hfile = await Bot(token=get_token()).get_file(
            file_id="AgACAgIAAxkBAAIBxmiGUBFD9oDC71HNnHv7ZeGZr_mpAAIB9DEbDF84SHKx38IRXUlvAQADAgADbQADNgQ"
        )
        buffer = BytesIO()
        await hfile.download_to_memory(out=buffer)
        buffer.seek(0)
        img = Image.open(buffer)
        assert img is not None

    def test_search(self) -> None:
        image = Image.open("tests/img/grune.jpg")
        vertexai.init()
        explainer = Explainer(model_name="vertex_ai/gemini-2.5-pro")
        result = explainer._explain(caption="", image=image)
        assert result.explanation is not None
