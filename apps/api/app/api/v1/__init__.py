from fastapi import APIRouter

from app.domains.admin.router import router as admin_router
from app.domains.ai.router import router as ai_router
from app.domains.auth.router import router as auth_router
from app.domains.broker.router import router as broker_router
from app.domains.corporate_actions.router import router as corporate_actions_router
from app.domains.events.router import router as events_router
from app.domains.fundamentals.router import router as fundamentals_router
from app.domains.knowledge_graph.router import router as knowledge_graph_router
from app.domains.macro.router import router as macro_router
from app.domains.market_data.router import router as market_router
from app.domains.news.router import router as news_router
from app.domains.options.router import router as options_router
from app.domains.paper_trading.router import router as paper_trading_router
from app.domains.portfolios.router import router as portfolios_router
from app.domains.rag.router import router as rag_router
from app.domains.risk.router import router as risk_router
from app.domains.simulation.router import router as simulation_router
from app.domains.users.router import router as users_router

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(portfolios_router)
api_v1_router.include_router(market_router)
api_v1_router.include_router(risk_router)
api_v1_router.include_router(simulation_router)
api_v1_router.include_router(events_router)
api_v1_router.include_router(macro_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(paper_trading_router)
api_v1_router.include_router(broker_router)
api_v1_router.include_router(options_router)
api_v1_router.include_router(fundamentals_router)
api_v1_router.include_router(corporate_actions_router)
api_v1_router.include_router(knowledge_graph_router)
api_v1_router.include_router(news_router)
api_v1_router.include_router(rag_router)
api_v1_router.include_router(ai_router)
