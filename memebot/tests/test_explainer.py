import asyncio
import queue
from asyncio import sleep
from asyncio.subprocess import Process
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import dspy
import google.pubsub_v1.types as gapic_types
import pytest
import vertexai
from google.cloud.pubsub_v1 import PublisherClient
from google.cloud.pubsub_v1.subscriber.message import Message as PubSubMessage
from PIL import Image
from pytest_mock import MockerFixture
from telegram import Bot, Message

from memebot.audio import NoAudioTrack, extract_audio_track
from memebot.config import MODEL_NAME, get_explainer_config, get_token
from memebot.explainer import (
    Explainer,
    ExplainSubscriber,
    IsAlreadyExplained,
    TooManyExplains,
    VideoExplainer,
    VideoInfoModel,
    VideoTooLarge,
    check_llm_quota,
    register_llm_request,
)
from tests.helpers import clean_subscription


class TestVideoInfoModel:
    def test_no_speech_model(self):
        info = VideoInfoModel(
            has_speech=False,
            lang="",
            transcript="",
            ru_translation="",
            de_translation="",
            grammar_explanation="",
        )
        assert info.has_speech is False
        assert info.lang == ""

    def test_german_speech_model(self):
        info = VideoInfoModel(
            has_speech=True,
            lang="DE",
            transcript="Wie geht es dir?",
            ru_translation="Как дела?",
            de_translation="",
            grammar_explanation="Modalverb + Infinitiv...",
        )
        assert info.lang == "DE"
        assert info.ru_translation == "Как дела?"
        assert info.de_translation == ""

    def test_non_german_speech_model(self):
        info = VideoInfoModel(
            has_speech=True,
            lang="EN",
            transcript="How are you?",
            ru_translation="",
            de_translation="Wie geht es dir?",
            grammar_explanation="Interrogativsatz...",
        )
        assert info.lang == "EN"
        assert info.de_translation == "Wie geht es dir?"
        assert info.ru_translation == ""

    def test_video_too_large_is_explainer_exception(self):
        from memebot.explainer import ExplainerException

        assert issubclass(VideoTooLarge, ExplainerException)


class TestLlmQuota:
    def _make_db(self, docs: list[dict]) -> MagicMock:
        """Mock Firestore client returning *docs* from the llm_requests query."""
        doc_mocks = []
        for d in docs:
            m = MagicMock()
            m.to_dict.return_value = d
            doc_mocks.append(m)
        db = MagicMock()
        db.collection.return_value.where.return_value.stream.return_value = iter(
            doc_mocks
        )
        return db

    def test_raises_already_explained_when_same_message_id(self):
        db = self._make_db([{"message_id": "42"}])
        with pytest.raises(IsAlreadyExplained):
            check_llm_quota(db, "42")

    def test_raises_too_many_when_25_different_messages(self):
        docs = [{"message_id": str(i)} for i in range(25)]
        db = self._make_db(docs)
        with pytest.raises(TooManyExplains):
            check_llm_quota(db, "99")

    def test_passes_when_under_limit_and_new_message_id(self):
        docs = [{"message_id": str(i)} for i in range(5)]
        db = self._make_db(docs)
        check_llm_quota(db, "99")  # must not raise

    def test_register_stores_message_id(self):
        db = MagicMock()
        register_llm_request(db, "42")
        stored = db.collection.return_value.document.return_value.set.call_args[0][0]
        assert stored["message_id"] == "42"
        assert "expiresAt" in stored


class TestExplainer:

    # No real Telegram token in testing env
    @pytest.mark.skip
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

    # No GCP auth in testing env
    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_broetchen(self) -> None:
        image = Image.open("tests/img/broetchen.jpg")
        vertexai.init()
        lm = dspy.LM(
            model="vertex_ai/gemini-2.5-pro",
            # model="openai/qwen2.5vl:3b",
            # api_base="http://localhost:11434/v1",
            # api_key="fake",
            temperature=0.0,
            max_tokens=16384,
        )
        dspy.configure(lm=lm)
        explainer = Explainer()
        result = await explainer._explain(caption="", image=image)
        assert result.explanation is not None

    # No GCP auth in testing env
    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_dolina(self) -> None:
        image = Image.open("tests/img/dolina.jpg")
        vertexai.init()
        lm = dspy.LM(
            model="vertex_ai/gemini-2.5-pro",
            temperature=0.0,
            max_tokens=16384,
        )
        dspy.configure(lm=lm)
        explainer = Explainer()
        result = await explainer._explain(caption="", image=image)
        assert result.explanation is not None

    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_squidward(self) -> None:
        image = Image.open("tests/img/squidward.jpg")
        vertexai.init()
        lm = dspy.LM(
            model="vertex_ai/gemini-2.5-pro",
            temperature=0.0,
            max_tokens=16384,
        )
        dspy.configure(lm=lm)
        explainer = Explainer()
        result = await explainer._explain(caption="", image=image)
        assert result.explanation is not None

    # No GCP auth in testing env
    @pytest.mark.skip
    @pytest.mark.asyncio
    async def test_search(self) -> None:
        image = Image.open("tests/img/ruhs.jpg")
        vertexai.init()
        lm = dspy.LM(
            model="vertex_ai/gemini-2.5-pro",
            # model="openai/qwen2.5vl:3b",
            # api_base="http://localhost:11434/v1",
            # api_key="fake",
            temperature=0.0,
            max_tokens=16384,
        )
        dspy.configure(lm=lm)
        explainer = Explainer()
        result = await explainer._explain(
            caption="Woman on the photo is Julia Ruhs", image=image
        )
        assert result.explanation is not None


class TestExplainSubscriber:
    @pytest.mark.xdist_group("pubsub")
    @pytest.mark.pubsub
    @pytest.mark.asyncio
    async def test_pulling(
        self,
        lm: dspy.LM,
        mocker: MockerFixture,
        explain_message: Message,
        pubsub: Process,
    ) -> None:
        _ = pubsub
        _ = lm
        explainer = ExplainSubscriber(loop=asyncio.get_running_loop())
        mock_pull_message = mocker.patch(
            "memebot.explainer.ExplainSubscriber.pull_message"
        )

        clean_subscription(get_explainer_config().subscription)

        # now publish a message
        publisher = PublisherClient()
        publish_future = publisher.publish(
            topic=get_explainer_config().topic,
            data=explain_message.to_json().encode("utf-8"),
            message_id=str(explain_message.message_id),
            chat_id=str(explain_message.chat.id),
        )
        _ = publish_future.result()

        with explainer.subscription():
            # it's async
            # the message is published, but the subscription task needs time to fetch
            # the message and process it
            await sleep(0.1)
        assert mock_pull_message.call_count == 1

    @pytest.mark.asyncio
    async def test_pull_message(
        self, mocker: MockerFixture, explain_message: Message
    ) -> None:
        loop = asyncio.get_running_loop()
        explainer = ExplainSubscriber(loop=loop)
        mock_explain = mocker.patch(
            "memebot.explainer.ExplainSubscriber.explain",
            new_callable=mocker.AsyncMock,
        )

        _raw_proto_pubbsub_message = gapic_types.PubsubMessage.pb()
        msg_pb = _raw_proto_pubbsub_message(
            data=explain_message.to_json().encode("utf-8"),
            ordering_key="",
            attributes={
                "chat_id": "0",
                "message_id": "777",
            },
        )
        pubsub_message = PubSubMessage(
            message=msg_pb,
            ack_id="0",
            delivery_attempt=0,
            request_queue=queue.Queue(),
        )
        await loop.run_in_executor(None, explainer.pull_message, pubsub_message)
        # explainer.pull_message(pubsub_message)
        assert mock_explain.call_count == 1


class TestVideoExplainer:
    """Unit tests for VideoExplainer.explain — all external I/O is mocked."""

    @pytest.fixture(autouse=True)
    def mock_firestore(self, mocker: MockerFixture):
        return mocker.patch("memebot.explainer.firestore.Client")

    @pytest.mark.asyncio
    async def test_returns_no_speech_when_no_audio_track(
        self, mocker: MockerFixture, video_explain_message: Message
    ):
        mocker.patch("memebot.explainer.check_llm_quota")
        mock_register = mocker.patch("memebot.explainer.register_llm_request")
        mocker.patch.object(
            VideoExplainer, "get_video_bytes", new=AsyncMock(return_value=b"fake_video")
        )
        mocker.patch(
            "memebot.explainer.extract_audio_track", side_effect=NoAudioTrack()
        )

        result = await VideoExplainer().explain(video_explain_message)

        assert result.has_speech is False
        assert result.lang == ""
        mock_register.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_video_info_on_success(
        self, mocker: MockerFixture, video_explain_message: Message
    ):
        mocker.patch("memebot.explainer.check_llm_quota")
        mock_register = mocker.patch("memebot.explainer.register_llm_request")
        mocker.patch.object(
            VideoExplainer, "get_video_bytes", new=AsyncMock(return_value=b"fake_video")
        )
        mocker.patch(
            "memebot.explainer.extract_audio_track", return_value=b"fake_audio"
        )
        expected = VideoInfoModel(
            has_speech=True,
            lang="DE",
            transcript="Wie geht es dir?",
            ru_translation="Как дела?",
            de_translation="",
            grammar_explanation="Modalverb...",
        )
        mocker.patch.object(
            VideoExplainer, "_explain", new=AsyncMock(return_value=expected)
        )

        result = await VideoExplainer().explain(video_explain_message)

        assert result == expected
        mock_register.assert_called_once()

    @pytest.mark.asyncio
    async def test_does_not_register_when_quota_exceeded(
        self, mocker: MockerFixture, video_explain_message: Message
    ):
        mocker.patch("memebot.explainer.check_llm_quota", side_effect=TooManyExplains())
        mock_register = mocker.patch("memebot.explainer.register_llm_request")

        with pytest.raises(TooManyExplains):
            await VideoExplainer().explain(video_explain_message)

        mock_register.assert_not_called()

    @pytest.mark.asyncio
    async def test_raises_video_too_large(
        self, mocker: MockerFixture, video_explain_message: Message
    ):
        mocker.patch("memebot.explainer.check_llm_quota")
        mocker.patch.object(
            VideoExplainer,
            "get_video_bytes",
            new=AsyncMock(side_effect=VideoTooLarge()),
        )

        with pytest.raises(VideoTooLarge):
            await VideoExplainer().explain(video_explain_message)


class TestExplainSubscriberVideo:

    @pytest.mark.asyncio
    async def test_no_speech_sends_correct_text(
        self, mocker: MockerFixture, video_explain_message: Message
    ):
        mocker.patch.object(
            VideoExplainer,
            "explain",
            new=AsyncMock(
                return_value=VideoInfoModel(
                    has_speech=False,
                    lang="",
                    transcript="",
                    ru_translation="",
                    de_translation="",
                    grammar_explanation="",
                )
            ),
        )
        bot_mock = mocker.MagicMock(spec=Bot)
        bot_mock.send_message = mocker.AsyncMock()
        mocker.patch("memebot.explainer.Bot", return_value=bot_mock)
        mocker.patch("memebot.explainer.get_token", return_value="fake")

        subscriber = ExplainSubscriber(loop=asyncio.get_event_loop())
        await subscriber._explain_video(video_explain_message)

        bot_mock.send_message.assert_called_once()
        assert (
            bot_mock.send_message.call_args.kwargs["text"]
            == "Голоса в видео не найдено."
        )

    @pytest.mark.asyncio
    async def test_german_speech_includes_transcript_translation_grammar(
        self, mocker: MockerFixture, video_explain_message: Message
    ):
        mocker.patch.object(
            VideoExplainer,
            "explain",
            new=AsyncMock(
                return_value=VideoInfoModel(
                    has_speech=True,
                    lang="DE",
                    transcript="Wie geht es dir?",
                    ru_translation="Как дела?",
                    de_translation="",
                    grammar_explanation="Gebrauch von 'es' als Platzhaltersubjekt.",
                )
            ),
        )
        bot_mock = mocker.MagicMock(spec=Bot)
        bot_mock.send_message = mocker.AsyncMock()
        mocker.patch("memebot.explainer.Bot", return_value=bot_mock)
        mocker.patch("memebot.explainer.get_token", return_value="fake")

        subscriber = ExplainSubscriber(loop=asyncio.get_event_loop())
        await subscriber._explain_video(video_explain_message)

        text = bot_mock.send_message.call_args.kwargs["text"]
        assert "### Транскрипт:" in text
        assert "Wie geht es dir?" in text
        assert "### Перевод:" in text
        assert "Как дела?" in text
        assert "### Грамматика:" in text
        assert "Перевод на немецкий" not in text  # DE branch must not contain this

    @pytest.mark.asyncio
    async def test_non_german_speech_includes_german_translation(
        self, mocker: MockerFixture, video_explain_message: Message
    ):
        mocker.patch.object(
            VideoExplainer,
            "explain",
            new=AsyncMock(
                return_value=VideoInfoModel(
                    has_speech=True,
                    lang="EN",
                    transcript="How are you?",
                    ru_translation="",
                    de_translation="Wie geht es dir?",
                    grammar_explanation="Gebrauch von 'es' als Platzhaltersubjekt.",
                )
            ),
        )
        bot_mock = mocker.MagicMock(spec=Bot)
        bot_mock.send_message = mocker.AsyncMock()
        mocker.patch("memebot.explainer.Bot", return_value=bot_mock)
        mocker.patch("memebot.explainer.get_token", return_value="fake")

        subscriber = ExplainSubscriber(loop=asyncio.get_event_loop())
        await subscriber._explain_video(video_explain_message)

        text = bot_mock.send_message.call_args.kwargs["text"]
        assert "### Транскрипт:" in text
        assert "How are you?" in text
        assert "### Перевод на немецкий:" in text
        assert "Wie geht es dir?" in text
        assert "### Грамматика:" in text

    @pytest.mark.asyncio
    async def test_video_too_large_sends_error_message(
        self, mocker: MockerFixture, video_explain_message: Message
    ):
        mocker.patch.object(
            VideoExplainer,
            "explain",
            new=AsyncMock(side_effect=VideoTooLarge()),
        )
        bot_mock = mocker.MagicMock(spec=Bot)
        bot_mock.send_message = mocker.AsyncMock()
        mocker.patch("memebot.explainer.Bot", return_value=bot_mock)
        mocker.patch("memebot.explainer.get_token", return_value="fake")

        subscriber = ExplainSubscriber(loop=asyncio.get_event_loop())
        await subscriber._explain_video(video_explain_message)

        text = bot_mock.send_message.call_args.kwargs["text"]
        assert "too large" in text.lower()


class TestVideoExplainerLive:
    """End-to-end test: real ffmpeg + real Gemini. Needs GCP ADC. Skipped in CI."""

    @pytest.mark.live
    @pytest.mark.asyncio
    async def test_frage_mp4(self):
        """
        Full pipeline on tests/img/frage.mp4:
          extract_audio_track → VideoExplainer._explain → print result.

        Assertions are intentionally soft — this is an observation test.
        Run with: pytest -m live -v -s tests/test_explainer.py::TestVideoExplainerLive::test_frage_mp4
        """
        vertexai.init()
        dspy.configure(
            lm=dspy.LM("vertex_ai/gemini-2.5-pro", temperature=0.0, max_tokens=32567),
            adapter=dspy.JSONAdapter(),
        )

        video_bytes = Path("tests/img/frage.mp4").read_bytes()
        audio_bytes = extract_audio_track(video_bytes)
        assert len(audio_bytes) > 0, "Expected non-empty audio from frage.mp4"

        info = await VideoExplainer()._explain(caption="", audio_bytes=audio_bytes)

        assert info.has_speech is True, "Expected speech in frage.mp4"
        assert info.lang, "Expected a non-empty language code"
        assert info.transcript, "Expected a non-empty transcript"
        if info.lang.upper() == "DE":
            assert info.ru_translation, "Expected Russian translation for German speech"
            assert (
                info.grammar_explanation
            ), "Expected grammar explanation for German speech"
        else:
            assert (
                info.de_translation
            ), "Expected German translation for non-German speech"
            assert info.grammar_explanation, "Expected grammar explanation"
