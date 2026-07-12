/**
 * Cloudflare Pages Edge Worker
 *
 * Intercepts HTML requests and injects window.CLIPMIND_API_URL so the frontend
 * knows where the Railway backend lives — without hardcoding it in the JS bundle.
 *
 * The CLIPMIND_API_URL environment variable is set in Cloudflare Pages dashboard.
 * Example value: https://clipmind-production.up.railway.app
 */
export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Fetch the original response from Cloudflare Pages static assets
    const response = await env.ASSETS.fetch(request);

    // Only inject into HTML documents
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('text/html')) {
      return response;
    }

    // Inject the API URL as a global variable before any scripts load
    const apiUrl = env.CLIPMIND_API_URL || '';
    const injectionScript = `<script>window.CLIPMIND_API_URL = ${JSON.stringify(apiUrl)};</script>`;

    const html = await response.text();
    const injected = html.replace('<head>', `<head>\n    ${injectionScript}`);

    return new Response(injected, {
      status: response.status,
      headers: response.headers,
    });
  },
};
