import vertexai
from PIL import Image

from memebot.explainer import Explainer


class TestPrompts:

    def test_search(self) -> None:
        image = Image.open("tests/img/grune.jpg")
        vertexai.init()
        explainer = Explainer(model_name="vertex_ai/gemini-2.5-pro")
        result = explainer._explain(caption="", image=image)
        assert result.explanation is not None
