from datetime import datetime, timedelta, timezone
from typing import Generator
from memebot.censor import SimpleTimeCensor
from pytest import mark


@mark.firestore
@mark.xdist_group("firestore")
class TestSimpleTimeCensor:

    def test_register(self, firestore_emulator: None) -> None:
        """Try to register # of messages above the limit and check the user can't send mesasges anymore"""
        _ = firestore_emulator
        censor = SimpleTimeCensor()
        uid = 100
        now = datetime.now(timezone.utc)
        for msg_id in range(2):
            censor.register(
                user_id=uid,
                message_id=msg_id,
                dt=now - timedelta(hours=2),
            )
        censor_result = censor.check(uid)
        assert censor_result.is_allowed == False

    @mark.parametrize(
        ("uid", "n_msg", "expected_is_allowed"),
        [
            (666, 0, True),
            (667, 1, True),
            (668, 2, False),
        ],
    )
    def test_check(
        self,
        firestore_emulator: None,
        uid: int,
        n_msg: int,
        expected_is_allowed: bool,
    ) -> None:
        _ = firestore_emulator
        censor = SimpleTimeCensor()
        now = datetime.now(timezone.utc)
        for msg_idx in range(n_msg):
            censor.register(
                user_id=uid,
                message_id=uid + msg_idx,
                dt=now
                - timedelta(hours=2)
                - timedelta(hours=msg_idx),
            )
        censor_result = censor.check(uid)
        assert censor_result.is_allowed == expected_is_allowed

    def test_check_mesasge(self, firestore_emulator: None) -> None:
        """Check the error message"""
        _ = firestore_emulator
        censor = SimpleTimeCensor()
        uid = 777
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
                user_id=uid,
                message_id=msg_idx,
                dt=now - timedelta(hours=msg_idx),
            )
        censor_result = censor.check(uid)
        assert censor_result.is_allowed == False
        assert f"{desired_time}" in censor_result.reason

    def test_check_last_mesasge(self, firestore_emulator: None) -> None:
        """Check the reason message when sending the last message for a day"""
        _ = firestore_emulator
        censor = SimpleTimeCensor()
        uid = 888
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
                user_id=uid,
                message_id=msg_idx,
                dt=now,
            )
        censor_result = censor.check(uid)
        assert censor_result.is_allowed == True
        assert f"{desired_time}" in censor_result.reason