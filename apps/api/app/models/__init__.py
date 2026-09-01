"""Import every model module so Base.metadata is fully populated before
init_models()/Alembic autogenerate runs."""

from app.models.ai import AIMessage, AISession, AIToolCall  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.backtest import Backtest  # noqa: F401
from app.models.broker import BrokerConnection  # noqa: F401
from app.models.event import Event  # noqa: F401
from app.models.macro import MacroIndicator  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.portfolio import Holding, Portfolio, Transaction  # noqa: F401
from app.models.security import Candle, Security  # noqa: F401
from app.models.user import User, UserPreferences  # noqa: F401
