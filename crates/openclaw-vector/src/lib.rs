//! OpenClaw Vector - 向量存储抽象层
//!
//! 提供统一的向量存储接口，支持多种后端：
//! - Memory (内存存储)
//! - LanceDB (嵌入式，零依赖)
//! - Qdrant (高性能独立服务)
//! - pgvector (PostgreSQL 扩展)
//! - Milvus (分布式向量数据库)
//! - SQLite-vec (轻量级嵌入)

pub mod store;
pub mod types;

pub use store::*;
pub use types::*;

pub use openclaw_core::{OpenClawError, Result};

pub use store::factory::{BackendConfig, VectorStoreFactory, init_default_factories, register_factory, get_factory, get_registered_factories};

#[cfg(feature = "lancedb")]
use store::lancedb::LanceDbStoreFactory;
#[cfg(feature = "qdrant")]
use store::qdrant::QdrantStoreFactory;
#[cfg(feature = "pgvector")]
use store::pgvector::PgVectorStoreFactory;
#[cfg(feature = "milvus")]
use store::milvus::MilvusStoreFactory;

pub fn init_all_factories() {
    init_default_factories();
    
    #[cfg(feature = "lancedb")]
    {
        let factory = std::sync::Arc::new(LanceDbStoreFactory) as store::factory::FactoryPtr;
        register_factory(factory);
        tracing::info!("Registered LanceDB vector store factory");
    }
    
    #[cfg(feature = "qdrant")]
    {
        let factory = std::sync::Arc::new(QdrantStoreFactory) as store::factory::FactoryPtr;
        register_factory(factory);
        tracing::info!("Registered Qdrant vector store factory");
    }
    
    #[cfg(feature = "pgvector")]
    {
        let factory = std::sync::Arc::new(PgVectorStoreFactory) as store::factory::FactoryPtr;
        register_factory(factory);
        tracing::info!("Registered PgVector store factory");
    }
    
    #[cfg(feature = "milvus")]
    {
        let factory = std::sync::Arc::new(MilvusStoreFactory) as store::factory::FactoryPtr;
        register_factory(factory);
        tracing::info!("Registered Milvus vector store factory");
    }
}
