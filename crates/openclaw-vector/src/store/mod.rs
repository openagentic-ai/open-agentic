//! 向量存储抽象层实现

pub mod factory;
#[cfg(feature = "lancedb")]
pub mod lancedb;
#[cfg(feature = "qdrant")]
pub mod qdrant;
#[cfg(feature = "pgvector")]
pub mod pgvector;
#[cfg(feature = "milvus")]
pub mod milvus;
mod memory;
mod sqlite;

pub use factory::*;

use async_trait::async_trait;
use openclaw_core::{OpenClawError, Result};
use std::sync::Arc;

#[cfg(feature = "lancedb")]
pub use lancedb::LanceDbStore;
pub use memory::MemoryStore;
#[cfg(feature = "pgvector")]
pub use pgvector::PgVectorStore;
#[cfg(feature = "qdrant")]
pub use qdrant::QdrantStore;
#[cfg(feature = "milvus")]
pub use milvus::MilvusStore;
pub use sqlite::SqliteStore;

use super::types::{Filter, SearchQuery, SearchResult, StoreStats, VectorItem};

/// 向量存储 Trait
#[async_trait]
pub trait VectorStore: Send + Sync {
    async fn upsert(&self, item: VectorItem) -> Result<()>;
    async fn upsert_batch(&self, items: Vec<VectorItem>) -> Result<usize>;
    async fn search(&self, query: SearchQuery) -> Result<Vec<SearchResult>>;
    async fn get(&self, id: &str) -> Result<Option<VectorItem>>;
    async fn delete(&self, id: &str) -> Result<()>;
    async fn delete_by_filter(&self, filter: Filter) -> Result<usize>;
    async fn stats(&self) -> Result<StoreStats>;
    async fn clear(&self) -> Result<()>;
}

#[derive(Debug, Clone)]
pub enum StoreBackend {
    Memory,
    #[cfg(feature = "lancedb")]
    LanceDB {
        path: std::path::PathBuf,
    },
    #[cfg(feature = "qdrant")]
    Qdrant {
        url: String,
        collection: String,
        api_key: Option<String>,
    },
    #[cfg(feature = "pgvector")]
    PgVector {
        url: String,
        table: String,
    },
    #[cfg(feature = "milvus")]
    Milvus {
        url: String,
        collection: String,
        dimension: Option<usize>,
    },
    SQLite {
        path: std::path::PathBuf,
        table: String,
    },
}

pub fn create_store(backend: StoreBackend) -> Result<Arc<dyn VectorStore>> {
    match backend {
        StoreBackend::Memory => Ok(Arc::new(MemoryStore::new())),
        #[cfg(feature = "lancedb")]
        StoreBackend::LanceDB { path: _ } => Err(OpenClawError::VectorStore(
            "LanceDB requires async initialization. Use create_store_async instead.".to_string(),
        )),
        #[cfg(feature = "qdrant")]
        StoreBackend::Qdrant { .. } => Err(OpenClawError::VectorStore(
            "Qdrant requires async initialization. Use create_store_async instead.".to_string(),
        )),
        #[cfg(feature = "pgvector")]
        StoreBackend::PgVector { .. } => Err(OpenClawError::VectorStore(
            "PgVector requires async initialization. Use create_store_async instead.".to_string(),
        )),
        #[cfg(feature = "milvus")]
        StoreBackend::Milvus { .. } => Err(OpenClawError::VectorStore(
            "Milvus requires async initialization. Use create_store_async instead.".to_string(),
        )),
        StoreBackend::SQLite { path, table } => {
            let store = SqliteStore::new(path, &table)?;
            Ok(Arc::new(store))
        }
    }
}

pub async fn create_store_async(backend: StoreBackend) -> Result<Arc<dyn VectorStore>> {
    match backend {
        StoreBackend::Memory => Ok(Arc::new(MemoryStore::new()) as Arc<dyn VectorStore>),
        #[cfg(feature = "lancedb")]
        StoreBackend::LanceDB { path } => {
            let store: LanceDbStore = LanceDbStore::new(&path, "vectors").await?;
            Ok(Arc::new(store) as Arc<dyn VectorStore>)
        }
        #[cfg(feature = "qdrant")]
        StoreBackend::Qdrant {
            url,
            collection,
            api_key,
        } => {
            let store: QdrantStore = QdrantStore::new(&url, &collection, 1536, api_key.as_deref()).await?;
            Ok(Arc::new(store) as Arc<dyn VectorStore>)
        }
        #[cfg(feature = "pgvector")]
        StoreBackend::PgVector { url, table } => {
            let store: PgVectorStore = PgVectorStore::new(&url, &table, 1536).await?;
            Ok(Arc::new(store) as Arc<dyn VectorStore>)
        }
        #[cfg(feature = "milvus")]
        StoreBackend::Milvus { url, collection, dimension } => {
            let store: MilvusStore = MilvusStore::new(&url, &collection, dimension.unwrap_or(1536)).await?;
            Ok(Arc::new(store) as Arc<dyn VectorStore>)
        }
        StoreBackend::SQLite { path, table } => {
            let store: SqliteStore = SqliteStore::new(path, &table)?;
            Ok(Arc::new(store) as Arc<dyn VectorStore>)
        }
    }
}
