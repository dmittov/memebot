from google.cloud.pubsub_v1 import SubscriberClient


def clean_subscription(subscription: str) -> None:
    subscriber = SubscriberClient()
    while subscriber.pull(
        subscription=subscription,
        max_messages=100,
        return_immediately=True,
    ):
        ...
