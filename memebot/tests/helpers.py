from google.cloud.pubsub_v1 import SubscriberClient
from google.api_core.exceptions import DeadlineExceeded


def clean_subscription(subscription: str) -> None:
    subscriber = SubscriberClient()
    try:
        while subscriber.pull(
            subscription=subscription,
            max_messages=100,
            timeout=0.1,  # make sure message doesn't appear in the next 100ms 
        ):
            ...
    except DeadlineExceeded:
        ...  # no more messages left
