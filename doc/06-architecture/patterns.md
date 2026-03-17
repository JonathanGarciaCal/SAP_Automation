# Architecture Patterns & Design Decisions

## COM Threading Model

### The Problem

SAP GUI's COM scripting API uses the **Apartment-Threaded** model:
- COM objects must be accessed from the same thread that created them
- COM calls are **blocking** and synchronous
- NiceGUI runs on the asyncio main thread (event loop)
- Calling blocking COM from asyncio → **deadlock or hang**

### The Solution: Command Queue + Dedicated COM Thread

```
Main Thread (asyncio/NiceGUI)
    ↓
    Create Command object
    ↓
    Put Command on queue
    ↓
    Create asyncio.Future
    ↓
    await future (non-blocking)
    ↓
    ... do other work ...
    ↓
    Future resolved → get result


Worker Thread (STA)
    ↓
    pythoncom.CoInitialize()
    ↓
    while True:
      1. Get Command from queue
      2. Execute COM method
      3. Resolve future via loop.call_soon_threadsafe()
```

### Implementation

**sap/bridge.py**:
- `QueueManager`: Manages worker thread and command queue
- `Command`: Data class for commands (method name + primitive args only)
- No COM object references cross thread boundaries

**sap/session.py**:
- All methods are async coroutines that return futures
- Internally enqueue commands to worker thread
- Wait for result asynchronously

### Why This Works

1. **No COM on main thread**: Main thread never touches COM → no deadlock
2. **Non-blocking**: asyncio never waits for COM → responsive UI
3. **Type-safe**: Only primitives on queue → no marshaling issues
4. **Testable**: Mock queue manager for unit tests

### Critical Rule

⚠️ **NEVER call SAP COM methods directly from NiceGUI handlers or asyncio tasks.**

Always use the session API's async methods, which internally queue to worker thread.

```python
# ❌ WRONG - Direct COM call (will hang/deadlock)
value = sap_app.obj.GetProcessInfo("value")

# ✅ CORRECT - Via queue to worker thread
value = await session.get_field_value("FIELD_ID")
```

---

## Configuration Schema

### Design Principles

1. **Environment-driven**: Config reads from YAML, overridden by env vars
2. **Validated at startup**: Pydantic catches errors early
3. **No hardcoded secrets**: Credentials come from env or prompt
4. **Type-safe**: All config values have types and defaults
5. **Single source**: One `RuntimeConfig` object accessed via `get_config()`

### Layers (Precedence Order)

```
1. Environment variables (SAP_USERNAME=...)
2. YAML config file (config.yaml)
3. Pydantic field defaults
```

### Usage

```python
from pathlib import Path
from config import initialize_config, get_config

# At startup
config = initialize_config(Path('config.yaml'))

# Anywhere in app
config = get_config()
port = config.app.port
client = config.sap.client
```

### Validation

Pydantic v2 validators ensure:
- Client number is valid SAP format
- Port is in valid range (1024-65535)
- Logging level is one of {DEBUG, INFO, WARNING, ERROR, CRITICAL}

---

## Command Pattern for Async COM

### Why Commands?

COM objects cannot be pickled or passed between threads. Instead:

1. Convert high-level operation → Command (method name + args)
2. Pass Command (data only) to queue
3. Worker thread deserializes and executes
4. Return result via asyncio.Future

### Command Structure

```python
@dataclass
class Command:
    module: str          # 'sap.session'
    method: str          # 'get_field_value'
    args: tuple         # ('FIELD_ID',)
    kwargs: dict        # {}
```

### Execution Path

```
UI Handler (main thread):
    → session.get_field_value('FIELD')
    → create Command
    → put on queue
    → return await future

Queue Worker (worker thread):
    → consume Command
    → com_session.objGetField(args)
    → loop.call_soon_threadsafe(future.set_result(value))
```

---

## Error Handling & Resilience

### Transient vs Permanent Errors

**Transient** (retry-able):
- Network timeout
- SAP server temporarily busy
- Session disconnect (auto-reconnect)

**Permanent** (fail fast):
- Invalid transaction code
- Permission denied
- Field not found
- Config error

### Retry Strategy

```python
async def retry_async(
    coro: Awaitable,
    max_attempts: int = 3,
    backoff_ms: float = 500.0
) -> Any:
    """Retry with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            return await coro
        except TransientError as e:
            if attempt == max_attempts - 1:
                raise
            wait_ms = backoff_ms * (2 ** attempt)  # 500ms, 1s, 2s
            await asyncio.sleep(wait_ms / 1000)
        except PermanentError:
            raise  # Don't retry
```

### Circuit Breaker (Phase 5)

If SAP is down:

```python
state = CircuitBreaker(
    failure_threshold=5,      # 5 consecutive failures → OPEN
    recovery_timeout=30,      # After 30s, try HALF_OPEN
    success_threshold=2        # 2 successes in HALF_OPEN → CLOSED
)

available = await state.call_async(session.connect())
if not available:
    show_error("SAP temporarily unavailable")
```

---

## Feature Flags

Enable/disable major features per phase:

```yaml
features:
  enable_screen_inspector: false   # Phase 2
  enable_script_runner: false      # Phase 3
  enable_report_engine: false      # Phase 4
```

In code:

```python
config = get_config()

if config.features.enable_screen_inspector:
    # Show inspector page
    @ui.page('/inspector')
    async def inspector_page():
        ...
```

---

## Testing Strategy

### Unit Tests

- Mock SAP connection for bridge tests
- Mock session for logic tests
- Validate config without SAP installation

```python
@pytest.fixture
async def mock_sap_session():
    """Mock session for testing."""
    session = AsyncMock()
    session.get_field_value.return_value = "12345"
    return session

@pytest.mark.asyncio
async def test_field_read(mock_sap_session):
    result = await mock_sap_session.get_field_value("FIELD")
    assert result == "12345"
```

### Integration Tests

- Start real queue manager
- Test command execution path
- Timeout after 5 seconds

```python
@pytest.mark.asyncio  
async def test_queue_manager_executes():
    mgr = QueueManager()
    mgr.start()
    
    future = asyncio.Future()
    cmd = Command("sap.session", "get_field_value", ("TEST",))
    mgr.enqueue(cmd, future)
    
    result = await asyncio.wait_for(future, timeout=5.0)
    assert result is not None
```

---

## Security

### Credential Handling

1. **Never hardcode in code**
2. **Never commit .env to git** (.env in .gitignore)
3. **Read from environment** at runtime
4. **Clear from memory** after authentication
5. **Log only hashed values** if needed

```python
# ❌ WRONG
config.sap.password = "MyPassword123"

# ✅ CORRECT
config.sap.password = os.getenv("SAP_PASSWORD")
```

### UI Security

- No sensitive data in browser logs
- No credentials in URL parameters
- No unencrypted data on disk

---

## Performance Considerations

### Async/Await Pattern

All I/O operations should be async to prevent UI blocking:

```python
# ❌ WRONG - Blocks UI for 5 seconds
def get_user(user_id):
    time.sleep(5)  # SAP query
    return user

# ✅ CORRECT - UI responsive
async def get_user(user_id):
    result = await asyncio.wait_for(
        session.get_field_value(f"USER_{user_id}"),
        timeout=5.0
    )
    return result
```

### Queue Performance

- Keep commands small (primitives only)
- Batch operations when possible
- Monitor queue depth (log warnings if > 50)

### Caching

```python
# Cache element tree for 5 seconds
cache_ttl = 5.0
last_tree = None
last_update = 0

async def get_elements():
    global last_tree, last_update
    if time.time() - last_update < cache_ttl:
        return last_tree
    last_tree = await inspector.get_element_tree()
    last_update = time.time()
    return last_tree
```

---

## References

- **Python asyncio**: https://docs.python.org/3/library/asyncio.html
- **Pydantic v2**: https://docs.pydantic.dev/latest/
- **pywin32 (COM)**: https://github.com/pywin32/pywin32
- **NiceGUI**: https://nicegui.io/
- **SAP GUI Scripting**: See `doc/02-sap-scripting/`
