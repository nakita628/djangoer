# Schema docs

![ER diagram](er.svg)

[Author](#author) · [Tag](#tag) · [Post](#post) · [Comment](#comment)

<details>
<summary>The whole schema as SQL</summary>

```sql
CREATE TABLE "blog_author" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "user_id" integer NULL UNIQUE REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "name" varchar(100) NOT NULL, "email" varchar(254) NOT NULL UNIQUE, "bio" text NOT NULL, "joined_at" datetime NOT NULL);

CREATE TABLE "blog_tag" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "label" varchar(50) NOT NULL UNIQUE);

CREATE TABLE "blog_post" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "author_id" bigint NOT NULL REFERENCES "blog_author" ("id") DEFERRABLE INITIALLY DEFERRED, "title" varchar(200) NOT NULL, "slug" varchar(200) NOT NULL, "body" text NOT NULL, "status" varchar(10) NOT NULL, "views" integer unsigned NOT NULL CHECK ("views" >= 0), "rating" decimal NULL, "metadata" text NOT NULL CHECK ((JSON_VALID("metadata") OR "metadata" IS NULL)), "published_at" datetime NULL, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, CONSTRAINT "post_author_slug_unique" UNIQUE ("author_id", "slug"));

CREATE TABLE "blog_post_tags" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "post_id" bigint NOT NULL REFERENCES "blog_post" ("id") DEFERRABLE INITIALLY DEFERRED, "tag_id" bigint NOT NULL REFERENCES "blog_tag" ("id") DEFERRABLE INITIALLY DEFERRED);

CREATE TABLE "blog_comment" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "post_id" bigint NOT NULL REFERENCES "blog_post" ("id") DEFERRABLE INITIALLY DEFERRED, "author_id" bigint NULL REFERENCES "blog_author" ("id") DEFERRABLE INITIALLY DEFERRED, "parent_id" bigint NULL REFERENCES "blog_comment" ("id") DEFERRABLE INITIALLY DEFERRED, "text" text NOT NULL, "approved" bool NOT NULL, "created_at" datetime NOT NULL);

CREATE INDEX "blog_post_author_id_dd7a8485" ON "blog_post" ("author_id");

CREATE INDEX "blog_post_slug_b95473f2" ON "blog_post" ("slug");

CREATE INDEX "post_status_published" ON "blog_post" ("status", "published_at");

CREATE UNIQUE INDEX "blog_post_tags_post_id_tag_id_4925ec37_uniq" ON "blog_post_tags" ("post_id", "tag_id");

CREATE INDEX "blog_post_tags_post_id_a1c71c8a" ON "blog_post_tags" ("post_id");

CREATE INDEX "blog_post_tags_tag_id_0875c551" ON "blog_post_tags" ("tag_id");

CREATE INDEX "blog_comment_post_id_580e96ef" ON "blog_comment" ("post_id");

CREATE INDEX "blog_comment_author_id_4f11e2e0" ON "blog_comment" ("author_id");

CREATE INDEX "blog_comment_parent_id_f2a027bb" ON "blog_comment" ("parent_id");
```

</details>

## Author

Table `blog_author`, app `blog`.

Someone who writes posts.

![Author and the models it relates to](tables/Author.svg)

| Column | Field | Type | Null | Key | Default | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `BigAutoField` | `integer` |  | PK | `autoincrement()` |  |
| `user_id` | `OneToOneField` | `integer` | yes | FK, unique |  |  |
| `name` | `CharField` | `varchar(100)` |  |  |  |  |
| `email` | `EmailField` | `varchar(254)` |  | unique |  | Where replies are sent |
| `bio` | `TextField` | `text` |  |  |  |  |
| `joined_at` | `DateTimeField` | `datetime` |  |  | `now()` |  |

Relations:

- [Post](#post).`author_id` → `id`, on delete cascade
- [Comment](#comment).`author_id` → `id`, on delete set null

## Tag

Table `blog_tag`, app `blog`.

![Tag and the models it relates to](tables/Tag.svg)

| Column | Field | Type | Null | Key | Default | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `BigAutoField` | `integer` |  | PK | `autoincrement()` |  |
| `label` | `SlugField` | `varchar(50)` |  | unique |  |  |

Relations:

- `posts` — many to many with [Post](#post)

## Post

Table `blog_post`, app `blog`.

An article, a draft until it is published.

![Post and the models it relates to](tables/Post.svg)

| Column | Field | Type | Null | Key | Default | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `BigAutoField` | `integer` |  | PK | `autoincrement()` |  |
| `author_id` | `ForeignKey` | `bigint` |  | FK |  |  |
| `title` | `CharField` | `varchar(200)` |  |  |  |  |
| `slug` | `SlugField` | `varchar(200)` |  |  |  |  |
| `body` | `TextField` | `text` |  |  |  |  |
| `status` | `PostStatus` | `varchar(10)` |  |  | `'draft'` |  |
| `views` | `PositiveIntegerField` | `integer unsigned` |  |  | `0` |  |
| `rating` | `DecimalField` | `decimal` | yes |  |  |  |
| `metadata` | `JSONField` | `text` |  |  | `dict()` |  |
| `published_at` | `DateTimeField` | `datetime` | yes |  |  |  |
| `created_at` | `DateTimeField` | `datetime` |  |  | `now()` |  |
| `updated_at` | `DateTimeField` | `datetime` |  |  | `now()` |  |

Indexes:

- index `blog_post_author_id_dd7a8485` on `author_id`
- index `blog_post_slug_b95473f2` on `slug`
- unique `post_author_slug_unique` on `author_id`, `slug`
- index `post_status_published` on `status`, `published_at`

Relations:

- `author_id` → [Author](#author).`id`, on delete cascade
- `tags` — many to many with [Tag](#tag)
- [Comment](#comment).`post_id` → `id`, on delete cascade

## Comment

Table `blog_comment`, app `blog`.

![Comment and the models it relates to](tables/Comment.svg)

| Column | Field | Type | Null | Key | Default | Description |
| --- | --- | --- | --- | --- | --- | --- |
| `id` | `BigAutoField` | `integer` |  | PK | `autoincrement()` |  |
| `post_id` | `ForeignKey` | `bigint` |  | FK |  |  |
| `author_id` | `ForeignKey` | `bigint` | yes | FK |  |  |
| `parent_id` | `ForeignKey` | `bigint` | yes | FK |  |  |
| `text` | `TextField` | `text` |  |  |  |  |
| `approved` | `BooleanField` | `bool` |  |  | `False` |  |
| `created_at` | `DateTimeField` | `datetime` |  |  | `now()` |  |

Indexes:

- index `blog_comment_post_id_580e96ef` on `post_id`
- index `blog_comment_author_id_4f11e2e0` on `author_id`
- index `blog_comment_parent_id_f2a027bb` on `parent_id`

Relations:

- `post_id` → [Post](#post).`id`, on delete cascade
- `author_id` → [Author](#author).`id`, on delete set null
- `parent_id` → [Comment](#comment).`id`, on delete cascade

# Enums

## PostStatus

| Name | Stored as |
| --- | --- |
| `DRAFT` | `draft` |
| `PUBLISHED` | `published` |
| `ARCHIVED` | `archived` |
