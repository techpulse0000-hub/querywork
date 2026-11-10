# Configured model and pricing

Verified 29 October 2026. Standard synchronous API rates, not Batch pricing.

- Generator: `gpt-4o-mini`.
- Grader: `gpt-4o-mini`.
- Input: USD 0.15 per million tokens.
- Output: USD 0.60 per million tokens.
- Tavily: USD 0.008 per credit, using the published pay-as-you-go rate. Basic search costs one credit per request.

Sources: [OpenAI GPT-4o mini model page](https://developers.openai.com/api/docs/models/gpt-4o-mini), [Tavily credits and pricing](https://docs.tavily.com/documentation/api-credits).

GPT-4o mini is the user's confirmed selection, distinct from the retired `o4-mini` reasoning model. A high reasoning-effort parameter is not sent for GPT-4o mini. The model is marked deprecated in the official documentation; account/model access is checked through the app's validation action.

The app reports estimates. OpenAI input caching and Tavily free credits or subscription rates may reduce actual charges. Generation, grading, retry usage, and provider billing can differ from a single query's displayed estimate; the provider invoice is authoritative. Rates can be edited and saved on the Environment page.
