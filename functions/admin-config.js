/**
 * Cloudflare Pages Function — serves at /admin-config
 * Returns ADMIN_CONFIG as JavaScript, reading secrets from CF env vars.
 *
 * Set these in Cloudflare Pages → Settings → Environment variables:
 *   ADMIN_SUPABASE_KEY  — Supabase service role key
 *   ADMIN_GH_TOKEN      — GitHub PAT with actions:write scope
 */
export async function onRequest(context) {
  const { env } = context;

  const config = {
    supabase_url: "https://xahazlzuxowamknucprs.supabase.co",
    supabase_key: env.ADMIN_SUPABASE_KEY || "",
    gh_token:     env.ADMIN_GH_TOKEN     || "",
    gh_repo:      "mpshunters/dealerhunters-app",
  };

  return new Response(
    `const ADMIN_CONFIG = ${JSON.stringify(config)};`,
    {
      headers: {
        "Content-Type": "application/javascript",
        "Cache-Control": "no-store",
      },
    }
  );
}
