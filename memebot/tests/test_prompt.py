import os
import dspy
import json
from PIL import Image
import vertexai
from pydantic import BaseModel, Field


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
        description="Give a meme explanation. Why is it funny or cute?",
    )


class ExplainPicture(dspy.Signature):
    """Your task is to analyse a meme. Your response must be in russian."""
    meme_image: dspy.Image = dspy.InputField(desc="The meme image")
    explanation: MemeInfo = dspy.OutputField()


class TestPrompts:

    def test_kolonie(self) -> None:
        image = Image.open("tests/img/kolonie.jpg")
        
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
