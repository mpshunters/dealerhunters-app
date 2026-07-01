export default {
  async scheduled(event, env, ctx) {
    const res = await fetch(
      'https://api.github.com/repos/mpshunters/dealerhunters-app/actions/workflows/daily_scrape.yml/dispatches',
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${env.GITHUB_PAT}`,
          'Accept': 'application/vnd.github+json',
          'X-GitHub-Api-Version': '2022-11-28',
          'Content-Type': 'application/json',
          'User-Agent': 'DealerHunters-CF-Worker',
        },
        body: JSON.stringify({ ref: 'main' }),
      }
    );

    if (!res.ok) {
      const body = await res.text();
      throw new Error(`GitHub API ${res.status}: ${body}`);
    }

    console.log(`Pipeline triggered at ${new Date().toISOString()}`);
  },
};
