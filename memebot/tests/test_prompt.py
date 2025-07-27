import os
from typing import List, Optional
import dspy
import json
from PIL import Image
import vertexai
from pydantic import BaseModel, Field

from memebot.retrievers import GermanNewsRetriever

class MemeSimpleInfo(BaseModel):
    explanation: str = Field(
        description=(
            "Explain this meme in a humorous and insightful way. "
            "Describe why it’s funny or cute, including any cultural "
            "references, visual elements, or wordplay involved."
        )
    )


class ContextInfo(BaseModel):
    lang: str = Field(
        description="Give the ISO 2-letter code for the majority of the text on the picture",
        example={"value": "en"},
    )
    has_person: bool = Field(
        description="Is there a famous person or a drawing of a famous person on the picture",
        example={"value": True},
    )
    has_animal: bool = Field(
        description="Is there an animal or drawing of an animal on the picture",
        example={"value": True},
    )
    search_query: str = Field(
        description=(
            "Given that understanding this meme depends on the latest "
            "developments in German news, suggest a specific Google search "
            "query that would help uncover the relevant context. The query "
            "must be in german."
        )
    )
    is_query: bool = Field(
        description=(
            "Does this meme make complete sense on its own, or does it seem "
            "like understanding it requires knowledge of recent news events "
            "in Germany?",
        ),
        example={"value": True},
    )


class MemeInfo(BaseModel):
    lang: str = Field(
        description="Give the ISO 2-letter code for the majority of the text on the picture",
        example={"value": "en"},
    )
    has_person: bool = Field(
        description="Is there a famous person or a drawing of a famous person on the picture",
        example={"value": True},
    )
    has_animal: bool = Field(
        description="Is there an animal or drawing of an animal on the picture",
        example={"value": True},
    )
    ru_translation: str = Field(
        description="Translate the text from the picture to russian",
    )
    grammar_explanation: str = Field(
        description="Explain all german B1+ grammar, ignore obvious grammar that is well known by people able to pass B1 exam.",
    )
    explanation: str = Field(
        description=(
            "Explain this meme in a humorous and insightful way. "
            "Describe why it’s funny or cute, including any cultural "
            "references, visual elements, or wordplay involved."
        )
    )

class ContextRequest(dspy.Signature):
    """Your task is to analyse a meme. Your response must be in russian."""
    meme_image: dspy.Image = dspy.InputField(desc="The meme image")
    context_request: ContextInfo = dspy.OutputField()


class ExplainPicture(dspy.Signature):
    """Your task is to analyse a meme. Your response must be in russian."""
    meme_image: dspy.Image = dspy.InputField(desc="The meme image")
    context: List[str] = dspy.InputField(desc="These news may be related to the meme and provide additional information.")
    explanation: MemeInfo = dspy.OutputField()


class SimpleExplainPicture(dspy.Signature):
    """You are given a meme. Analyze its content.
    Your response must be in russian."""
    meme_image: dspy.Image = dspy.InputField(desc="The meme image")
    explanation: MemeSimpleInfo = dspy.OutputField()



class TestPrompts:

    def test_explain(self) -> None:
        image = Image.open("tests/img/presidents.jpg")
        
        vertexai.init()
        lm = dspy.LM(
            "vertex_ai/gemini-2.5-pro",
            temperature = 0.0,
            max_tokens = 8192,
        )
        dspy.configure(lm=lm)
        explainer = dspy.Predict(ExplainPicture)
        result = explainer(meme_image=dspy.Image.from_PIL(image))

        assert result is not None

    def test_wels(self) -> None:
        image = Image.open("tests/img/wels.jpg")
        
        vertexai.init()
        lm = dspy.LM(
            "vertex_ai/gemini-2.5-pro",
            temperature = 0.0,
            max_tokens = 8192,
        )
        dspy.configure(lm=lm)
        explainer = dspy.Predict(ContextRequest)
        result = explainer(meme_image=dspy.Image.from_PIL(image))

        assert result is not None


    def test_request(self) -> None:
        image = Image.open("tests/img/presidents.jpg")
        
        vertexai.init()
        lm = dspy.LM(
            "vertex_ai/gemini-2.5-pro",
            temperature = 0.0,
            max_tokens = 8192,
        )
        dspy.configure(lm=lm)
        explainer = dspy.Predict(ContextRequest)
        result = explainer(meme_image=dspy.Image.from_PIL(image))

        assert result is not None

    def test_search(self) -> None:
        image = Image.open("tests/img/labubu.jpg")

        vertexai.init()
        lm = dspy.LM(
            "vertex_ai/gemini-2.5-pro",
            temperature = 0.0,
            max_tokens = 8192,
        )
        dspy.configure(lm=lm)
        query_extractor = dspy.Predict(ContextRequest)
        img = dspy.Image.from_PIL(image)
        query = query_extractor(meme_image=img).context_request

        retriver = GermanNewsRetriever()
        assert query.is_query is True
        documents = retriver(query.search_query)
        assert len(documents) > 0

        explainer = dspy.Predict(ExplainPicture)
        result = explainer(meme_image=img, context=documents)
        assert result.explanation is not None
