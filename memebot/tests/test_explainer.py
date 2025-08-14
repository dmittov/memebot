from io import BytesIO

import dspy
import pytest
import vertexai
from PIL import Image
from telegram import Bot

from memebot.config import get_token
from memebot.explainer import Explainer


@pytest.mark.asyncio
class TestExplainer:

    async def test_image(self) -> None:
        hfile = await Bot(token=get_token()).get_file(
            file_id="AgACAgIAAxkBAAIBxmiGUBFD9oDC71HNnHv7ZeGZr_mpAAIB9DEbDF84SHKx38IRXUlvAQADAgADbQADNgQ"
        )
        buffer = BytesIO()
        await hfile.download_to_memory(out=buffer)
        buffer.seek(0)
        img = Image.open(buffer)
        assert img is not None

    @pytest.mark.skip
    async def test_search(self) -> None:
        image = Image.open("tests/img/grune.jpg")
        vertexai.init()
        lm = dspy.LM(
            "vertex_ai/gemini-2.5-pro",
            temperature=0.0,
            max_tokens=16384,
        )
        explainer = Explainer(lm=lm)
        result = await explainer._explain(caption="", image=image)
        assert result.explanation is not None
