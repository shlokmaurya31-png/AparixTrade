"""Import every model module so Base.metadata is fully populated before
init_models()/Alembic autogenerate runs."""

from app.models.ai import AIMessage, AISession, AIToolCall  # noqa: F401
from app.models.audit import AuditLog  # noqa: F401
from app.models.backtest import Backtest  # noqa: F401
from app.models.broker import BrokerConnection  # noqa: F401
from app.models.corporate_action import CorporateAction  # noqa: F401
from app.models.document_embedding import DocumentEmbedding  # noqa: F401
from app.models.event import Event  # noqa: F401
from app.models.fundamentals import FinancialStatement  # noqa: F401
from app.models.knowledge_graph import Commodity, Location, SecurityCommodityLink, SecurityLocationLink  # noqa: F401
from app.models.macro import MacroIndicator  # noqa: F401
from app.models.macro_release import MacroIndicatorRelease  # noqa: F401
from app.models.news import NewsArticle  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.portfolio import Holding, Portfolio, Transaction  # noqa: F401
from app.models.security import Candle, Security  # noqa: F401
from app.models.user import User, UserPreferences  # noqa: F401
