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
        for msg_idx in range(n_msg):
            censor.register(
                user_id=uid,
                message_id=uid + msg_idx,
                dt=datetime.now(timezone.utc)
                - timedelta(hours=2)
                - timedelta(hours=msg_idx),
            )
        censor_result = censor.check(uid)
        assert censor_result.is_allowed == expected_is_allowed
