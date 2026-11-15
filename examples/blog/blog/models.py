from django.conf import settings
from django.db import models


class Author(models.Model):
    """Someone who writes posts."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, help_text="Where replies are sent")
    bio = models.TextField(blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Tag(models.Model):
    label = models.SlugField(unique=True)

    def __str__(self):
        return self.label


class Post(models.Model):
    """An article, a draft until it is published."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="posts")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    body = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    views = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    tags = models.ManyToManyField(Tag, related_name="posts", blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "published_at"], name="post_status_published")]
        constraints = [
            models.UniqueConstraint(fields=["author", "slug"], name="post_author_slug_unique")
        ]

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(Author, on_delete=models.SET_NULL, null=True, blank=True)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    text = models.TextField()
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.text[:40]
