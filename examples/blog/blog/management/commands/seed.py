import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from blog.models import Author, Comment, Post, Tag


class Command(BaseCommand):
    help = "Fill the example database with authors, posts, tags and comments."

    def handle(self, *args, **options):
        rng = random.Random(42)
        Comment.objects.all().delete()
        Post.objects.all().delete()
        Author.objects.all().delete()
        Tag.objects.all().delete()

        names = ["Ann Lee", "Ben Okafor", "Chika Sato", "Dmitri Volkov", "Eva Lind", "Farid Nasser"]
        authors = [
            Author.objects.create(
                name=name,
                email=f"{name.split()[0].lower()}@example.com",
                bio=f"{name} writes about Django.",
            )
            for name in names
        ]
        tags = [
            Tag.objects.create(label=label)
            for label in ["django", "orm", "sql", "python", "testing", "deploy"]
        ]
        topics = [
            "QuerySets",
            "Migrations",
            "Signals",
            "Managers",
            "Transactions",
            "Indexes",
            "Aggregation",
            "Prefetching",
        ]
        now = timezone.now()
        posts = []
        for index in range(40):
            topic = topics[index % len(topics)]
            status = rng.choice(
                [
                    Post.Status.DRAFT,
                    Post.Status.PUBLISHED,
                    Post.Status.PUBLISHED,
                    Post.Status.ARCHIVED,
                ]
            )
            post = Post.objects.create(
                author=rng.choice(authors),
                title=f"{topic} in practice, part {index // len(topics) + 1}",
                slug=f"{topic.lower()}-{index}",
                body=f"Notes on {topic.lower()}.",
                status=status,
                views=rng.randint(0, 5000),
                rating=rng.choice([None, 3.5, 4.0, 4.5, 5.0]),
                metadata={"reading_minutes": rng.randint(2, 15)},
                published_at=now - timedelta(days=rng.randint(1, 300))
                if status != Post.Status.DRAFT
                else None,
            )
            post.tags.set(rng.sample(tags, rng.randint(1, 3)))
            posts.append(post)
        for index in range(120):
            Comment.objects.create(
                post=rng.choice(posts),
                author=rng.choice([None, *authors]),
                text=f"Comment {index + 1}",
                approved=rng.random() > 0.3,
            )
        self.stdout.write(
            self.style.SUCCESS("Seeded 6 authors, 6 tags, 40 posts and 120 comments.")
        )
