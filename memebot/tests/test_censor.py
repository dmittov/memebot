from datetime import datetime, timedelta, timezone

from pytest_mock import MockerFixture
from memebot.censor import CensorResult, SimpleTimeCensor
from pytest import mark, fixture
from google.cloud import firestore
from requests import Response

from memebot.message import MessageUtil


@fixture
def censor(mocker: MockerFixture) -> SimpleTimeCensor:
    """SimpleTimeCensor with mocked firestore connection"""
    mock_firestore = mocker.MagicMock(spec=firestore.Client)
    mocker.patch.object(
        SimpleTimeCensor,
        "db",
        new_callable=mocker.PropertyMock,
        return_value=mock_firestore,
    )
    return SimpleTimeCensor()


@mark.firestore
@mark.xdist_group("firestore")
class TestSimpleTimeCensorFirestore:

    def test_register(self, firestore_emulator: None) -> None:
        """Try to register # of messages above the limit and check the user can't send mesasges anymore"""
        _ = firestore_emulator
        censor = SimpleTimeCensor()
        user_id = 100
        now = datetime.now(timezone.utc)
        for msg_id in range(2):
            censor.register(
                user_id=user_id,
                message_id=msg_id,
                dt=now - timedelta(hours=2),
            )
        censor_result = censor.check(user_id=user_id)
        assert censor_result.is_allowed == False

    @mark.parametrize(
        ("user_id", "n_msg", "expected_is_allowed"),
        [
            (666, 0, True),
            (667, 1, True),
            (668, 2, False),
        ],
    )
    def test_check(
        self,
        firestore_emulator: None,
        user_id: int,
        n_msg: int,
        expected_is_allowed: bool,
    ) -> None:
        _ = firestore_emulator
        censor = SimpleTimeCensor()
        now = datetime.now(timezone.utc)
        for msg_idx in range(n_msg):
            censor.register(
                user_id=user_id,
                message_id=user_id + msg_idx,
                dt=now - timedelta(hours=2) - timedelta(hours=msg_idx),
            )
        censor_result = censor.check(user_id)
        assert censor_result.is_allowed == expected_is_allowed

    def test_check_mesasge(self, firestore_emulator: None) -> None:
        """Check the error message"""
        _ = firestore_emulator
        censor = SimpleTimeCensor()
        user_id = 777
        now = datetime.now(timezone.utc)
        desired_time = (
            # Local bt timezone / Berlin time
            now.astimezone(SimpleTimeCensor.tz)
            # 1 message has the current time, the second one which is 1 hr older
            # hits the threshold
            - timedelta(hours=SimpleTimeCensor.n_message_limit - 1)
            + SimpleTimeCensor.time_horizon
        ).replace(second=0, microsecond=0)
        for msg_idx in range(SimpleTimeCensor.n_message_limit):
            censor.register(
                user_id=user_id,
                message_id=msg_idx,
                dt=now - timedelta(hours=msg_idx),
            )
        censor_result = censor.check(user_id)
        assert censor_result.is_allowed == False
        assert f"{desired_time}" in censor_result.reason

    def test_check_last_mesasge(self, firestore_emulator: None) -> None:
        """Check the reason message when sending the last message for a day"""
        _ = firestore_emulator
        censor = SimpleTimeCensor()
        user_id = 888
        now = datetime.now(timezone.utc)
        # desired time = now + time_horizon
        # ingest n_message_limit - 1 messages with now timestamp
        desired_time = (
            # Local bt timezone / Berlin time
            now.astimezone(SimpleTimeCensor.tz)
            + SimpleTimeCensor.time_horizon
        ).replace(second=0, microsecond=0)
        for msg_idx in range(SimpleTimeCensor.n_message_limit - 1):
            censor.register(
                user_id=user_id,
                message_id=msg_idx,
                dt=now,
            )
        censor_result = censor.check(user_id)
        assert censor_result.is_allowed == True
        assert f"{desired_time}" in censor_result.reason


class TestSimpleTimeCensor:
    def test_post(self, mocker: MockerFixture, censor: SimpleTimeCensor) -> None:
        mocker.patch.object(
            censor,
            "check",
            return_value=CensorResult(is_allowed=True),
            autospec=True,
        )
        mocker.patch.object(
            censor,
            "register",
            return_value=None,
            autospec=True,
        )
        message = dict(message_id=0)
        response = mocker.MagicMock(spec=Response)
        response.json = lambda: dict(result=message)

        MessageUtilMock = mocker.patch("memebot.censor.MessageUtil")
        message_util_mock = MessageUtilMock.return_value
        forward_message_mock = message_util_mock.forward_message
        forward_message_mock.return_value = response
        send_message_mock = message_util_mock.send_message
        
        # patched_forward_message = mocker.patch.object(
        #     MessageUtil,
        #     "forward_message",
        #     return_value=response,
        #     autospec=True,
        # )
        censor.post(chat_id=1, user_id=1, message=message)
        assert forward_message_mock.call_count == 1
        assert send_message_mock.call_count == 1
