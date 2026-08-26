# ChatGPT web canary setup

The web profile is not active yet. It requires a separate stable HTTPS canary origin so the legacy connector can remain available.

## Activation gate

1. Obtain a stable canary domain that can run alongside the legacy endpoint.
2. Copy `profiles/web/profile.json.example` to `profiles/web/profile.json` and replace the example URL with the HTTPS origin only, without `/mcp`.
3. Materialize and run `doctor web`.
4. Start the web profile on `127.0.0.1:7677` and forward the stable domain to that port.
5. Verify protected-resource and authorization-server metadata, DCR, PKCE S256, issuer, resource, and audience.
6. Inspect `/mcp` with MCP Inspector before creating the ChatGPT app.

## ChatGPT Developer Mode

1. On ChatGPT web, enable Developer Mode under Settings → Security and login.
2. Create a private developer-mode app using `https://<canary-domain>/mcp`.
3. Review every discovered tool name, description, schema, annotation, and server instruction.
4. Approve OAuth using the web profile's Owner password.
5. Start a new conversation and explicitly select the canary app before the first prompt.

After any metadata or authentication change, restart/deploy the server, select Refresh on the app, confirm the new metadata, and start a new test conversation. Do not assume an existing conversation reloads the contract.

Secure MCP Tunnel remains an R&D path because DevSpace issue #182 describes an OAuth issuer/resource mismatch when the OpenAI-hosted resource URI differs from DevSpace's public authorization origin.
