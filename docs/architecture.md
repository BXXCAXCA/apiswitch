# APISwitch Architecture

APISwitch is a modular monolith.

```text
Client / SDK / Agent
        |
        v
FastAPI Gateway
        |
Protocol Normalizer
        |
Router & Scoring Engine
        |
Provider Adapter Registry
        |
OpenAI / Anthropic / Gemini / Compatible Providers
```

The first-stage implementation uses a Mock Provider to validate the full request path without external API keys.
