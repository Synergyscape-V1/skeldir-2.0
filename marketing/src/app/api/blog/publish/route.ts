import { NextRequest, NextResponse } from 'next/server';
import { getStore } from '@netlify/blobs';

export const runtime = 'nodejs';

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 80);
}

export async function POST(request: NextRequest) {
  // Auth check
  const authHeader = request.headers.get('authorization');
  const token = authHeader?.replace('Bearer ', '');
  if (token !== process.env.BLOG_PUBLISH_TOKEN) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let body: { title?: string; content?: string; excerpt?: string; category?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON' }, { status: 400 });
  }

  const { title, content, excerpt, category } = body;
  if (!title || !content) {
    return NextResponse.json({ error: 'title and content are required' }, { status: 400 });
  }

  const now = new Date();
  const publishDate = now.toISOString().split('T')[0];
  const slug = slugify(title);
  const id = `ai-${Date.now()}`;

  const article = {
    id,
    slug,
    title,
    subtitle: excerpt ?? '',
    category: (category as 'Attribution' | 'Budget Planning') ?? 'Attribution',
    excerpt: excerpt ?? content.slice(0, 200).replace(/#+\s/g, '').replace(/\n/g, ' '),
    readTimeMinutes: Math.max(1, Math.round(content.split(' ').length / 200)),
    publishDate,
    heroImagePath: '/images/resources/ai-article-hero.png',
    heroImageAlt: title,
    isFeaturedHero: false,
    author: 'Skeldir AI',
    content,
  };

  const store = getStore('blog-posts');
  await store.setJSON(slug, article);

  return NextResponse.json({ success: true, slug, url: `https://skeldir.com/resources/${slug}` }, { status: 201 });
}
