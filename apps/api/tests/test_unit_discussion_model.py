"""Regression test for the self-referential discussion thread mapping.

`replies` was declared with `remote_side=[id]`, which configures the MANY-to-one
side. That made `discussion.replies` resolve to the PARENT row instead of the
child collection, so root threads always reported `replies is None` and
`reply_count` was permanently 0 in the discussion APIs.
"""

from models.discussion import QuestionDiscussion
from sqlalchemy import inspect


def test_replies_is_a_collection_and_parent_is_scalar():
    rels = inspect(QuestionDiscussion).relationships

    assert rels["replies"].uselist is True, (
        "replies must be the one-to-many child collection"
    )
    assert rels["parent"].uselist is False, (
        "parent must be the many-to-one scalar side"
    )


def test_replies_and_parent_are_two_sides_of_one_relationship():
    rels = inspect(QuestionDiscussion).relationships
    assert rels["replies"].back_populates == "parent"
    assert rels["parent"].back_populates == "replies"


def test_deleting_a_thread_cascades_to_its_replies():
    """A deleted root thread must not leave orphaned replies behind."""
    cascade = inspect(QuestionDiscussion).relationships["replies"].cascade
    assert cascade.delete is True
    assert cascade.delete_orphan is True
