# A2A (Agent-to-Agent) Protocol -- Complete Analysis

## Research Date: 2026-04-11
## Protocol Version Analyzed: v1.0.0 (latest released)
## Governing Body: Linux Foundation (contributed by Google)
## License: Apache 2.0

---

## 1. Protocol Overview

The Agent2Agent (A2A) Protocol is an open standard for inter-agent communication and interoperability, designed to enable independent, potentially opaque AI agent systems to collaborate regardless of framework, language, or vendor. Originally announced by Google Cloud on April 9, 2025, the protocol reached v1.0 and is now governed by the Linux Foundation with 150+ supporting organizations.

### 1.1 Key Goals

- **Interoperability**: Bridge communication between disparate agentic systems
- **Collaboration**: Enable task delegation, context exchange, and joint problem-solving
- **Discovery**: Dynamic capability discovery via Agent Cards
- **Flexibility**: Synchronous, streaming (SSE), and async (push notification) interaction modes
- **Security**: Enterprise-grade, built on standard web security (HTTPS, OAuth 2.0, OpenID Connect)
- **Asynchronicity**: Native support for long-running tasks and human-in-the-loop

### 1.2 Guiding Principles

- **Simple**: Reuses HTTP, JSON-RPC 2.0, SSE, gRPC -- no novel transport
- **Enterprise Ready**: Standard auth, tracing, monitoring patterns
- **Async First**: Designed for long-running tasks and HITL
- **Modality Agnostic**: Text, files, structured data, audio/video references
- **Opaque Agents**: No access to each other's internal state, memory, or tools

### 1.3 Transport and Protocol Bindings

A2A v1.0 supports three protocol bindings:

| Binding | Transport | Description |
|---------|-----------|-------------|
| **JSON-RPC** | HTTP/1.1+ | JSON-RPC 2.0 over HTTPS, primary binding |
| **gRPC** | HTTP/2 | Protocol Buffers, high-performance strongly-typed |
| **HTTP+JSON/REST** | HTTP/1.1+ | RESTful endpoints, simpler integration |

---

## 2. Architecture and Roles

### 2.1 Client-Server Model

- **A2A Client (Client Agent)**: An app, service, or AI agent that delegates requests to remote agents
- **A2A Server (Remote Agent)**: Processes incoming tasks via HTTP endpoints and returns results

Key architectural principle: agents are **opaque** -- they do not share internal memory, tools, or direct resource access with each other. Communication happens entirely through the A2A protocol's structured messages.

### 2.2 Relationship to MCP (Model Context Protocol)

A2A and MCP are **complementary, not competing**:

| Aspect | MCP (Anthropic) | A2A (Google/LF) |
|--------|-----------------|------------------|
| **Purpose** | Agent-to-Tool connectivity | Agent-to-Agent collaboration |
| **Interaction Target** | Tools, APIs, databases, resources | Autonomous agent systems |
| **Characteristics** | Structured I/O, stateless primitives | Stateful, multi-turn, autonomous |
| **Analogy** | Gives an agent its tools | Lets agents work as a team |

**Typical combined pattern**: An A2A client agent delegates a task to an A2A server agent. The server agent internally uses MCP to interact with tools, APIs, and data sources needed to fulfill the A2A task.

---

## 3. Data Model (Complete)

### 3.1 Core Objects

#### 3.1.1 Task

The fundamental unit of work. Stateful, with a defined lifecycle.

```
Task {
  id: string              // Required. Unique ID (UUID), server-generated
  contextId: string       // Optional. Groups related interactions
  status: TaskStatus      // Required. Current status including state + message
  artifacts: Artifact[]   // Optional. Output artifacts
  history: Message[]      // Optional. Interaction history
  metadata: object        // Optional. Custom key/value metadata
}
```

#### 3.1.2 TaskStatus

```
TaskStatus {
  state: TaskState        // Required. Current lifecycle state
  message: Message        // Optional. Message associated with status
  timestamp: timestamp    // Optional. ISO 8601 when status was recorded
}
```

#### 3.1.3 TaskState (Lifecycle States)

| State | Type | Description |
|-------|------|-------------|
| `TASK_STATE_UNSPECIFIED` | Unknown | Indeterminate state |
| `TASK_STATE_SUBMITTED` | Initial | Task acknowledged by server |
| `TASK_STATE_WORKING` | In-progress | Actively being processed |
| `TASK_STATE_INPUT_REQUIRED` | Interrupted | Agent needs additional user input |
| `TASK_STATE_AUTH_REQUIRED` | Interrupted | Authentication required to proceed |
| `TASK_STATE_COMPLETED` | Terminal | Finished successfully |
| `TASK_STATE_FAILED` | Terminal | Finished with error |
| `TASK_STATE_CANCELED` | Terminal | Canceled before completion |
| `TASK_STATE_REJECTED` | Terminal | Agent decided not to perform the task |

**State Machine**:
```
                          +---> COMPLETED
                          |
SUBMITTED ---> WORKING ---+---> FAILED
                |    ^    |
                |    |    +---> CANCELED
                v    |    |
          INPUT_REQUIRED  +---> REJECTED
                |
                v
          AUTH_REQUIRED
```

Terminal states cannot accept further messages. Interrupted states (INPUT_REQUIRED, AUTH_REQUIRED) allow the client to send follow-up messages to resume processing.

#### 3.1.4 Message

One unit of communication between client and server.

```
Message {
  messageId: string          // Required. Unique ID (UUID)
  contextId: string          // Optional. Associates with context
  taskId: string             // Optional. Associates with task
  role: Role                 // Required. ROLE_USER or ROLE_AGENT
  parts: Part[]              // Required. Content container
  metadata: object           // Optional. Custom metadata
  extensions: string[]       // Optional. Extension URIs
  referenceTaskIds: string[] // Optional. Referenced task IDs for context
}
```

#### 3.1.5 Role

| Value | Description |
|-------|-------------|
| `ROLE_UNSPECIFIED` | Unspecified |
| `ROLE_USER` | Message from client to server |
| `ROLE_AGENT` | Message from server to client |

#### 3.1.6 Part

Content container. Must contain exactly one of: `text`, `raw`, `url`, `data`.

```
Part {
  // Exactly one of (OneOf):
  text: string       // String content (text part)
  raw: bytes         // Raw file bytes (base64 in JSON)
  url: string        // URL pointing to file content
  data: any          // Arbitrary structured JSON data

  // Optional common fields:
  metadata: object   // Metadata for the part
  filename: string   // Optional filename (e.g. "document.pdf")
  mediaType: string  // MIME type (e.g. "text/plain", "image/png")
}
```

**v1.0 Breaking Change**: Parts no longer use a `kind` discriminator field. Instead, the JSON member name itself identifies the type:
- TextPart: `{ "text": "Hello, world!" }`
- FilePart: `{ "raw": "iVBORw0KGgo...", "filename": "diagram.png", "mediaType": "image/png" }`
- DataPart: `{ "data": { "key": "value" }, "mediaType": "application/json" }`

#### 3.1.7 Artifact

Task output container.

```
Artifact {
  artifactId: string    // Required. Unique within task
  name: string          // Optional. Human-readable name
  description: string   // Optional. Human-readable description
  parts: Part[]         // Required. Content (at least one part)
  metadata: object      // Optional. Custom metadata
  extensions: string[]  // Optional. Extension URIs
}
```

### 3.2 Streaming Event Objects

#### 3.2.1 TaskStatusUpdateEvent

Communicates task lifecycle state changes during streaming.

```
TaskStatusUpdateEvent {
  taskId: string        // Required
  contextId: string     // Required
  status: TaskStatus    // Required. New status
  final: boolean        // Optional. If true, terminal event
  metadata: object      // Optional
}
```

#### 3.2.2 TaskArtifactUpdateEvent

Delivers new/updated artifacts during streaming.

```
TaskArtifactUpdateEvent {
  taskId: string        // Required
  contextId: string     // Required
  artifact: Artifact    // Required. The artifact
  append: boolean       // Optional. Append to previous artifact with same ID
  lastChunk: boolean    // Optional. Final chunk of artifact
  metadata: object      // Optional
}
```

#### 3.2.3 StreamResponse

Wrapper for all streaming responses. Must contain exactly one of:

```
StreamResponse {
  // Exactly one of (OneOf):
  task: Task                              // Full task state
  message: Message                        // Agent message
  statusUpdate: TaskStatusUpdateEvent     // Status change event
  artifactUpdate: TaskArtifactUpdateEvent // Artifact update event
}
```

### 3.3 Agent Discovery Objects

#### 3.3.1 AgentCard

Self-describing manifest for an agent. Published at `/.well-known/agent-card.json`.

```
AgentCard {
  name: string                    // Required. Human-readable name
  description: string             // Required. Purpose description
  url: string                     // Required. Base URL
  interfaces: AgentInterface[]    // Required. Protocol bindings
  provider: AgentProvider         // Optional. Service provider info
  version: string                 // Required. Agent version
  documentationUrl: string        // Optional. Docs URL
  capabilities: AgentCapabilities // Required. Feature support
  securitySchemes: map<string, SecurityScheme>  // Optional. Auth schemes
  securityRequirements: SecurityRequirement[]    // Optional. Auth requirements
  defaultInputModes: string[]     // Required. Supported input media types
  defaultOutputModes: string[]    // Required. Supported output media types
  skills: AgentSkill[]            // Required. Advertised skills
  signatures: AgentCardSignature[] // Optional. JWS signatures
}
```

#### 3.3.2 AgentCapabilities

```
AgentCapabilities {
  streaming: boolean           // Optional. Supports streaming responses
  pushNotifications: boolean   // Optional. Supports push notifications
  extensions: AgentExtension[] // Optional. Supported extensions
  extendedAgentCard: boolean   // Optional. Supports authenticated extended card
}
```

#### 3.3.3 AgentSkill

```
AgentSkill {
  id: string                    // Required. Unique skill identifier
  name: string                  // Required. Human-readable name
  description: string           // Required. Detailed description
  tags: string[]                // Required. Capability keywords
  examples: string[]            // Optional. Example prompts/scenarios
  inputModes: string[]          // Optional. Overrides agent defaults
  outputModes: string[]         // Optional. Overrides agent defaults
  securityRequirements: SecurityRequirement[] // Optional
}
```

#### 3.3.4 AgentInterface

```
AgentInterface {
  url: string              // Required. HTTPS URL for this interface
  protocolBinding: string  // Required. "JSONRPC" | "GRPC" | "HTTP+JSON"
  tenant: string           // Optional. Tenant ID
  protocolVersion: string  // Required. A2A version (e.g. "1.0")
}
```

#### 3.3.5 AgentCardSignature (v1.0)

Cryptographic identity verification using JSON Web Signatures (JWS, RFC 7515).

```
AgentCardSignature {
  protected: string   // Required. Base64url-encoded JWS Protected Header
  signature: string   // Required. Base64url-encoded signature
  header: object      // Optional. JWS Unprotected Header
}
```

Protected header must include: `alg` (e.g. "ES256", "RS256"), `typ` ("JOSE"), `kid` (key ID).

### 3.4 Push Notification Objects

#### 3.4.1 PushNotificationConfig

```
PushNotificationConfig {
  url: string                  // Required. Webhook URL
  authentication: AuthenticationInfo  // Optional. Auth for webhook
  id: string                   // Server-assigned config ID
}
```

#### 3.4.2 Push Notification Payload

Uses the same `StreamResponse` format as streaming operations. Sent as HTTP POST to the webhook URL with authentication headers.

---

## 4. Protocol Operations (All Methods)

### 4.1 Method Mapping Reference

| Functionality | JSON-RPC Method | gRPC Method | REST Endpoint |
|---------------|----------------|-------------|---------------|
| Send message | `SendMessage` | `SendMessage` | `POST /message:send` |
| Stream message | `SendStreamingMessage` | `SendStreamingMessage` | `POST /message:stream` |
| Get task | `GetTask` | `GetTask` | `GET /tasks/{id}` |
| List tasks | `ListTasks` | `ListTasks` | `GET /tasks` |
| Cancel task | `CancelTask` | `CancelTask` | `POST /tasks/{id}:cancel` |
| Subscribe to task | `SubscribeToTask` | `SubscribeToTask` | `POST /tasks/{id}:subscribe` |
| Create push config | `CreateTaskPushNotificationConfig` | same | `POST /tasks/{id}/pushNotificationConfigs` |
| Get push config | `GetTaskPushNotificationConfig` | same | `GET /tasks/{id}/pushNotificationConfigs/{configId}` |
| List push configs | `ListTaskPushNotificationConfigs` | same | `GET /tasks/{id}/pushNotificationConfigs` |
| Delete push config | `DeleteTaskPushNotificationConfig` | same | `DELETE /tasks/{id}/pushNotificationConfigs/{configId}` |
| Get extended card | `GetExtendedAgentCard` | same | `GET /extendedAgentCard` |

### 4.2 SendMessage (Primary Operation)

**Purpose**: Send a message to initiate or continue a task.

**Request** (SendMessageRequest):
```json
{
  "message": {
    "messageId": "msg-uuid",
    "role": "ROLE_USER",
    "parts": [{"text": "Book me a flight to Tokyo"}]
  },
  "configuration": {
    "acceptedOutputModes": ["text/plain"],
    "historyLength": 10
  }
}
```

**Response** (SendMessageResponse): Returns either a `Task` object (for stateful work) or a `Message` object (for stateless responses).

```json
{
  "task": {
    "id": "task-uuid",
    "contextId": "context-uuid",
    "status": {
      "state": "TASK_STATE_INPUT_REQUIRED",
      "message": {
        "role": "ROLE_AGENT",
        "parts": [{"text": "Where would you like to fly from?"}]
      }
    }
  }
}
```

### 4.3 SendStreamingMessage

Same request as SendMessage. Server responds with HTTP 200 + `Content-Type: text/event-stream`. Each SSE event's `data` field contains a JSON-RPC response wrapping a `StreamResponse`.

### 4.4 GetTask

Retrieve current state of a task by ID. Supports `historyLength` parameter to limit returned history.

### 4.5 ListTasks

List tasks with optional filtering by `contextId`, `status`, `statusTimestampAfter`. Supports pagination.

### 4.6 CancelTask

Cancel a task in progress. Returns the updated Task. Fails with `TaskNotCancelableError` if task is in terminal state.

### 4.7 SubscribeToTask

Subscribe to updates for an existing non-terminal task. Returns a stream of `StreamResponse` events (same as SendStreamingMessage).

### 4.8 SendMessageConfiguration

```
SendMessageConfiguration {
  acceptedOutputModes: string[]              // Client's accepted output media types
  taskPushNotificationConfig: PushNotificationConfig  // Push notification setup
  historyLength: integer                     // Max history messages to return
}
```

---

## 5. Agent Discovery

### 5.1 Discovery Mechanisms

1. **Well-Known URI**: `https://{domain}/.well-known/agent-card.json`
2. **Registries/Catalogs**: Curated agent directories
3. **Direct Configuration**: Pre-configured Agent Card URLs

### 5.2 Discovery Flow

```
Client                              Server
  |                                    |
  |-- GET /.well-known/agent-card.json -->
  |                                    |
  |<-- AgentCard (JSON) --------------|
  |                                    |
  | [Parse skills, capabilities,       |
  |  auth requirements]                |
  |                                    |
  |-- Authenticate (OAuth/API key) --->|
  |                                    |
  |-- GET /extendedAgentCard --------->|  (optional, if supported)
  |                                    |
  |<-- Extended AgentCard ------------|
```

### 5.3 Extended Agent Card

If `capabilities.extendedAgentCard` is true, authenticated clients can retrieve a more detailed Agent Card containing:
- Additional skills not in the public card
- More detailed capability information (rate limits, quotas)
- Organization-specific or user-specific configuration
- Different details based on authentication level

### 5.4 Capability Negotiation

Clients negotiate capabilities through:
- **Input/Output Modes**: `defaultInputModes` / `defaultOutputModes` on AgentCard; per-skill overrides
- **acceptedOutputModes**: Client declares what it can handle in SendMessageConfiguration
- **Capabilities flags**: `streaming`, `pushNotifications`, `extendedAgentCard`

---

## 6. Task Lifecycle (Detailed)

### 6.1 Response Types

Agents choose between two response types:

- **Message (Stateless)**: For immediate, self-contained interactions. No task state management.
- **Task (Stateful)**: For substantial, trackable work with defined lifecycle.

### 6.2 Agent Complexity Levels

- **Message-only Agents**: Always respond with Messages. Use `contextId` for continuity.
- **Task-capable Agents**: Create Tasks for complex operations. May start with Messages for negotiation, then transition to Tasks.

### 6.3 Context Continuity

The `contextId` groups multiple Tasks and Messages into a logical session:
- First message: agent responds with new `contextId`
- Subsequent messages: client includes same `contextId` to continue
- Client can use `taskId` to continue specific task
- Client can use `contextId` without `taskId` for new task in same context

### 6.4 Multi-Turn Patterns

**Context Continuity**:
- Tasks maintain context via `contextId`
- Clients MAY include `contextId` in subsequent messages
- Agents MUST reject mismatching `contextId`/`taskId`

**Input Required State**:
- Agent transitions task to `INPUT_REQUIRED`
- Client sends new message with same `taskId` and `contextId`
- Agent resumes processing

**Follow-up Messages**:
- Clients can reference related tasks via `referenceTaskIds`
- Agents use referenced tasks to understand context

---

## 7. Streaming and Asynchronous Operations

### 7.1 SSE Streaming

**When to use**: Real-time feedback, incremental results, short task execution (minutes).

**Flow**:
1. Server declares `capabilities.streaming: true` in Agent Card
2. Client calls `SendStreamingMessage` (or `POST /message:stream`)
3. Server responds with HTTP 200, `Content-Type: text/event-stream`
4. Server pushes `StreamResponse` events (status updates, artifact chunks)
5. Stream terminates when task reaches terminal/interrupted state

**Event types in stream**:
- `Task`: Full task state snapshot
- `Message`: Agent communication
- `TaskStatusUpdateEvent`: State transition notifications
- `TaskArtifactUpdateEvent`: Artifact delivery (supports chunked delivery via `append`/`lastChunk`)

### 7.2 Push Notifications (Webhooks)

**When to use**: Long-running tasks (hours/days), mobile apps, serverless, disconnected clients.

**Flow**:
1. Server declares `capabilities.pushNotifications: true` in Agent Card
2. Client creates push config via `CreateTaskPushNotificationConfig`
3. Server sends HTTP POST to webhook URL on significant state changes
4. Client retrieves full task state via `GetTask`

**Trigger events**: Terminal states (completed, failed, canceled, rejected), interrupted states (input-required, auth-required).

**Security requirements**:
- Agent MUST include auth credentials in webhook requests
- Agent SHOULD validate webhook URLs (prevent SSRF)
- Client MUST validate webhook authenticity
- Client MUST respond with 2xx to acknowledge
- Client SHOULD process idempotently

### 7.3 Task Subscription

For tasks already created (e.g., via previous `SendMessage`), clients can subscribe to updates via `SubscribeToTask`. Returns same stream format as `SendStreamingMessage`.

---

## 8. Authentication and Security Model

### 8.1 Transport Security

- **HTTPS Mandate**: All production A2A communication over HTTPS
- **TLS 1.2+**: Modern cipher suites required
- **Server Identity**: Clients verify TLS certificates

### 8.2 Authentication

A2A delegates authentication to standard web mechanisms:

- **No Identity in Payload**: Identity established at HTTP transport layer
- **Agent Card Declaration**: `securitySchemes` and `securityRequirements` fields
- **Out-of-Band Credential Acquisition**: OAuth flows, key distribution external to A2A
- **HTTP Header Transmission**: `Authorization: Bearer <TOKEN>` or `API-Key: <KEY_VALUE>`

Supported schemes (aligned with OpenAPI Specification):
- OAuth 2.0 / OpenID Connect
- API Keys
- HTTP Basic/Bearer
- Custom schemes

### 8.3 Agent Card Signing

v1.0 introduces cryptographic signing of Agent Cards using JWS (RFC 7515):
- Ensures card authenticity and integrity
- Uses JSON Canonicalization (RFC 8785) for deterministic payload
- Supports key discovery via JWKS URLs
- Clients SHOULD verify signatures when present

### 8.4 Enterprise Security Features

- **Multi-tenancy**: `tenant` field in AgentInterface and operation requests
- **Distributed Tracing**: OpenTelemetry, W3C Trace Context headers
- **Comprehensive Logging**: taskId, sessionId, correlation IDs, trace context
- **Metrics**: Request/error rates, task latency, resource utilization
- **Auditing**: Significant event logging

---

## 9. Error Handling

### 9.1 Error Categories

- **Authentication Errors**: Invalid/missing credentials (401/UNAUTHENTICATED)
- **Authorization Errors**: Insufficient permissions (403/PERMISSION_DENIED)
- **Validation Errors**: Invalid request data
- **A2A-Specific Errors**: Protocol-level errors

### 9.2 A2A Error Code Mappings

| A2A Error Type | JSON-RPC Code | gRPC Status | HTTP Status |
|---------------|---------------|-------------|-------------|
| `TaskNotFoundError` | -32001 | NOT_FOUND | 404 |
| `TaskNotCancelableError` | -32002 | FAILED_PRECONDITION | 409 |
| `PushNotificationNotSupportedError` | -32003 | UNIMPLEMENTED | 400 |
| `UnsupportedOperationError` | -32004 | UNIMPLEMENTED | 400 |
| `ContentTypeNotSupportedError` | -32005 | INVALID_ARGUMENT | 400 |
| `InvalidAgentCardError` | -32006 | INVALID_ARGUMENT | 400 |
| `ExtendedAgentCardNotConfiguredError` | -32007 | FAILED_PRECONDITION | 400 |
| `ExtensionSupportRequiredError` | -32008 | FAILED_PRECONDITION | 400 |
| `VersionNotSupportedError` | -32009 | UNIMPLEMENTED | 400 |

---

## 10. Protocol Extensions

A2A supports protocol extensibility via Extensions:

- Extensions identified by URIs (should include version info)
- Declared in `AgentCapabilities.extensions`
- Referenced in Messages and Artifacts via `extensions` field
- Breaking changes require new URIs
- Unsupported extensions: agent ignores unless marked `required`

---

## 11. Multi-Agent Communication Patterns

### 11.1 Direct Delegation

Client agent discovers and delegates to a single specialist agent:
```
Client Agent --[SendMessage]--> Specialist Agent
                                     |
Client Agent <--[Task/Message]------+
```

### 11.2 Orchestrated Multi-Agent

Orchestrator decomposes tasks and delegates to specialists:
```
User ---> Orchestrator Agent
              |
              +--[A2A]--> Flight Agent
              |
              +--[A2A]--> Hotel Agent
              |
              +--[A2A]--> Activity Agent
              |
          Synthesize Results
              |
User <--- Orchestrator Agent
```

### 11.3 Chain Pattern

Agents chain to progressively refine outputs:
```
Client --[A2A]--> Agent A --[A2A]--> Agent B --[A2A]--> Agent C
                                                           |
Client <-------------------------------------------[result]
```

### 11.4 Collaborative Pattern

Agents reference each other's tasks via `referenceTaskIds`:
```
Agent A creates Task 1
Agent B creates Task 2 (references Task 1)
Agent C creates Task 3 (references Tasks 1 and 2)
```

---

## 12. Implementation Ecosystem

### 12.1 Official SDKs (5 languages)

- **Python**: `a2a-python` (primary, most mature)
- **JavaScript/TypeScript**: `a2a-js`
- **Java**: `a2a-java`
- **Go**: `a2a-go`
- **.NET**: `a2a-dotnet`

### 12.2 Platform Integrations

- **Google Cloud**: Agent Development Kit (ADK), Agent Engine
- **Microsoft Azure**: Azure AI Foundry, Copilot Studio
- **Amazon Web Services**: Amazon Bedrock AgentCore Runtime
- **LangChain**: Native A2A support in LangSmith

### 12.3 Adoption

- 150+ organizations supporting the standard
- 22,000+ GitHub stars
- Production deployments in supply chain, financial services, insurance, IT operations
- Supported by Salesforce, SAP, Atlassian, ServiceNow, and many more

---

## 13. Academic Research

### 13.1 Key Papers

- **"A Survey of Agent Interoperability Protocols"** (Ehtesham et al., 2025): Comparative analysis of MCP, ACP, A2A, and ANP protocols covering interaction modes, discovery, communication patterns, security
- **"Building A Secure Agentic AI Application Leveraging A2A Protocol"** (Habler et al., 2025): Comprehensive security analysis
- **"Improving Google A2A Protocol: Protecting Sensitive Data"** (2025): Analysis of gaps in handling payment credentials and identity documents
- **"A Study on the MCP x A2A Framework"**: How the two protocols complement each other for practical agent ecosystems

### 13.2 Key Research Findings

- A2A fills a critical gap between tool-level integration (MCP) and agent-level collaboration
- The opaque agent model aligns naturally with enterprise security paradigms
- Primary challenge identified: sensitive data handling in multi-agent contexts
- The protocol's HTTP-based design enables standard enterprise observability

---

## 14. Implications for RLang (Reasoning Language Design)

### 14.1 Core Concepts to Express

A reasoning language covering A2A communication needs constructs for:

1. **Agent Identity and Discovery**
   - Agent Card declaration (name, capabilities, skills, auth)
   - Discovery via well-known URIs or registries
   - Capability negotiation

2. **Task Lifecycle Management**
   - Task creation, state transitions, completion
   - State machine: submitted -> working -> completed/failed/canceled
   - Interrupted states: input-required, auth-required
   - Terminal state detection and handling

3. **Message Exchange**
   - Multi-part messages (text, file, data)
   - Role-based communication (user/agent)
   - Context continuity via contextId/taskId

4. **Artifact Production and Consumption**
   - Named, typed output artifacts
   - Streaming artifact delivery (append/lastChunk chunking)

5. **Streaming and Async Patterns**
   - SSE stream subscription and event handling
   - Push notification webhook setup and processing
   - Task subscription for existing tasks

6. **Multi-Agent Orchestration**
   - Delegation patterns
   - Result synthesis from multiple agents
   - Task reference chains (referenceTaskIds)
   - Context sharing across agent boundaries

### 14.2 Type System Requirements

The language should express:
- `TaskState` as a discriminated union / sum type
- `Part` as a tagged union (text | raw | url | data)
- `StreamResponse` as a tagged union (task | message | statusUpdate | artifactUpdate)
- `Role` as an enum
- `AgentCard` as a structured record type
- State transition constraints (which transitions are valid)

### 14.3 Control Flow Requirements

- Pattern matching on task states for branching logic
- Async/await or callback patterns for streaming
- Error handling with A2A-specific error types
- Retry logic with exponential backoff (for push notifications)
- Timeout handling for long-running tasks

### 14.4 Security Constructs

- Auth scheme declaration and credential handling
- TLS requirement enforcement
- Webhook URL validation
- Agent Card signature verification

---

## 15. Canonical Example: Multi-Turn Flight Booking

```
// 1. Client discovers agent
GET https://travel-agent.example.com/.well-known/agent-card.json
-> AgentCard { name: "Travel Agent", skills: ["flight-booking", "hotel-booking"], ... }

// 2. Client sends initial request
POST /message:send
{
  "message": {
    "role": "ROLE_USER",
    "parts": [{"text": "Book me a flight to Tokyo"}],
    "messageId": "msg-1"
  }
}

// 3. Agent requests more input
Response: {
  "task": {
    "id": "task-123",
    "contextId": "ctx-456",
    "status": {
      "state": "TASK_STATE_INPUT_REQUIRED",
      "message": {
        "role": "ROLE_AGENT",
        "parts": [{"text": "Where would you like to fly from and on what dates?"}]
      }
    }
  }
}

// 4. Client provides input (continuing task)
POST /message:send
{
  "message": {
    "taskId": "task-123",
    "contextId": "ctx-456",
    "role": "ROLE_USER",
    "parts": [{"text": "From San Francisco, departing May 15, returning May 22"}],
    "messageId": "msg-2"
  }
}

// 5. Agent completes with artifact
Response: {
  "task": {
    "id": "task-123",
    "status": { "state": "TASK_STATE_COMPLETED" },
    "artifacts": [{
      "artifactId": "booking-1",
      "name": "Flight Confirmation",
      "parts": [{
        "data": {
          "confirmation": "FLT-789",
          "departure": "SFO",
          "arrival": "NRT",
          "dates": { "depart": "2026-05-15", "return": "2026-05-22" }
        },
        "mediaType": "application/json"
      }]
    }]
  }
}
```

---

## 16. References

- Official Specification: https://a2a-protocol.org/latest/specification/
- GitHub Repository: https://github.com/a2aproject/A2A
- Google Announcement Blog: https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
- A2A and MCP Comparison: https://a2a-protocol.org/latest/topics/a2a-and-mcp/
- Life of a Task: https://a2a-protocol.org/latest/topics/life-of-a-task/
- Streaming and Async: https://a2a-protocol.org/latest/topics/streaming-and-async/
- Enterprise Features: https://a2a-protocol.org/latest/topics/enterprise-ready/
- Google Cloud Blog (v1.0 upgrade): https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade
- IBM Explainer: https://www.ibm.com/think/topics/agent2agent-protocol
- Linux Foundation Adoption: https://www.linuxfoundation.org/press/a2a-protocol-surpasses-150-organizations
- Survey Paper (arxiv): https://arxiv.org/html/2505.02279v1
- Security Analysis Paper (arxiv): https://arxiv.org/html/2505.12490v3
