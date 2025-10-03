# 0. Импорт библиотек
## основные
import os
import streamlit as st
from typing import List

## Qdrant и Langchain
from qdrant_client import QdrantClient
from langchain_huggingface import HuggingFaceEmbeddings

from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain.schema import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough

# ----------------------
# 1️⃣ Настройки и секреты
# ----------------------
# Все секреты теперь хранятся в st.secrets
# Убедитесь, что в вашем файле .streamlit/secrets.toml есть эти ключи:
# QDRANT_URL = "https://your-cluster-url.cloud.qdrant.io"
# QDRANT_API_KEY = "your-qdrant-api-key"
# GROQ_API_KEY = "your-groq-api-key"
# HUGGINGFACEHUB_API_TOKEN = "your-huggingface-token" # Добавим для эмбеддингов

os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
os.environ["HUGGINGFACEHUB_API_TOKEN"] = st.secrets.get("HUGGINGFACEHUB_API_TOKEN", "")

COLLECTION_NAME = "shows_collection"

# ----------------------
# 2️⃣ Подключение к Qdrant Cloud и настройка Retriever
# ----------------------


# Используем @st.cache_resource для эффективного управления подключениями
@st.cache_resource
def get_qdrant_client():
    """Инициализирует и возвращает клиент для Qdrant Cloud."""
    client = QdrantClient(
        url=st.secrets["QDRANT_URL"],
        api_key=st.secrets["QDRANT_API_KEY"],
    )
    return client


@st.cache_resource
# def get_embeddings_model():
#     """Загружает модель для эмбеддингов ЛОКАЛЬНО."""
#     model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
#     model_kwargs = {'device': 'cpu'}
#     encode_kwargs = {'normalize_embeddings': True} # Убрал batch_size, он не всегда нужен здесь


#     # Используем оригинальный класс для локальных моделей
#     return HuggingFaceEmbeddings(
#         model_name=model_name,
#         model_kwargs=model_kwargs,
#         encode_kwargs=encode_kwargs,
#     )
def get_embeddings_model():
    """Загружает модель для эмбеддингов через Hugging Face Endpoint API."""

    # Просто передаем ID модели. Langchain сам сформирует правильный URL.
    model_name = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

    return HuggingFaceEndpointEmbeddings(
        repo_id=model_name,  # <-- Используем параметр 'repo_id'
        huggingfacehub_api_token=st.secrets["HUGGINGFACEHUB_API_TOKEN"],
    )


def format_docs(docs: List) -> str:
    """Форматирует найденные документы для передачи в LLM."""
    return "\n".join(f"{d.metadata.get('title')}: {d.page_content}" for d in docs)


# Инициализация компонентов
try:
    client = get_qdrant_client()
    embeddings_model = get_embeddings_model()

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings_model,
    )

    retriever = vector_store.as_retriever(
        search_type="similarity", search_kwargs={"k": 5}
    )

    st.sidebar.success("✅ Подключение к Qdrant Cloud и модели успешно!")

except Exception as e:
    st.error(f"❌ Ошибка подключения к Qdrant или моделям: {e}")
    st.stop()


# ----------------------
# 3️⃣ Настройка LLM (уже через API)
# ----------------------
@st.cache_resource
def get_llm():
    """Инициализирует и возвращает LLM модель (уже работает через API)."""
    return ChatGroq(model="llama-3.3-70b-versatile", temperature=0.25, max_tokens=1000)


llm = get_llm()


# ----------------------
# 4️⃣ Prompt для RAG + RAG-цепочка
# ----------------------
rag_prompt_template = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """Привет, дружище! Представь, что ты волшебник, который находит идеальные сериалы.
Стиль:
- Легко и от души, как с близким другом
- Юмор и забавные комментарии про закулисье
- Подчеркивай уникальные фишки (странные повороты, неожиданные герои)
- На русском, структурировано, с эмодзи 🎉
- Расскажи, кому сериал особенно подойдет
- Все ответы выводи с четкой разбивкой на пункты и сохранением порядка.
- Выдавай рекомендации только из базы данных.
- Если запрос не относится к сериалам, отвечай, что такую магию ты не знаешь.

Помни: Юмор должен быть добрым и приятным — создаем атмосферу близкого друга, который обожает сериалы.

Примеры подобных ответов, которые я жду от тебя:
---
Вопрос: Посоветуй сериал про любовь с драмой
Ответ:
О, дружище! Есть у меня пара сериалов в запасе на такой случай. Давай я расскажу, чем они интересны:

Сериал первый: "Бахар"! (только название)
1. О чем: Мелодрама о такой любви, что не сдается даже перед бурями судьбы, еще и с таким заносчивым финалом, что глаза откроются шире, чем у совы! 😄
2. Почему именно этот сериал: страсть, слезы, необычный финал - что еще надо для счастья?
3. Кому понравится: всем чувственным особам, фанатам Керема Бюрсина и эмоциональных качелей 🎢💔.

Сериал второй: «Иван Никогда»! (только название)
1. О чем: настоящая сага с лайфхаками от бывшего чиновника, который теперь учится летать (и не только самолетом!). Представь рой пчел в багажнике — и это только начало 😜!
2. Почему именно этот сериал: немного магии, необычный персонаж и приключения.
3. Кому понравится: бюджетникам и чиновникам и любителям прочих остросюжетных линий

""",
        ),
        (
            "human",
            "Вот подборка сериалов, которые могут подойти:\n{context}\n\nА теперь, основываясь на этой подборке, ответь на мой вопрос: {question}",
        ),
    ]
)

# Создаем RAG цепочку
rag_chain = (
    {
        "context": retriever | format_docs,
        "question": RunnablePassthrough(),
    }
    | rag_prompt_template
    | llm
    | StrOutputParser()
)


# ----------------------
# 5️⃣ Streamlit интерфейс
# ----------------------
st.set_page_config(page_title="🎬 Умный поиск сериалов", layout="wide")
st.title("🎬 Умный поиск сериалов по описанию 🧞‍♂️")

user_query = st.text_area(
    "Расскажи, что бы ты хотел посмотреть 👀",
    height=100,
    placeholder="Например, сериал про гениального, но циничного врача-диагноста",
)
with st.sidebar:
    top_k_slider = st.slider(
        "🍿Количество сериалов в подборке:",
        min_value=1,
        max_value=20,
        value=5,
    )


if st.button("✨ Найти идеальный сериал"):
    if user_query.strip():
        with st.spinner("🧞‍♀️Джинн колдует над рекомендациями..."):

            # --- ИЗМЕНЕНИЕ 1: Получаем документы с оценками ---
            # Используем vector_store.similarity_search_with_score вместо retriever
            docs_with_scores = vector_store.similarity_search_with_score(
                user_query, k=top_k_slider
            )

            # Если ничего не найдено, выходим
            if not docs_with_scores:
                st.warning("Ничего не найдено в базе по такому запросу 😢")
                st.stop()

            # --- ИЗМЕНЕНИЕ 2: Разделяем документы и оценки для удобства ---
            # Это понадобится для передачи контекста в RAG и для отображения
            docs = [doc for doc, score in docs_with_scores]

            # Формируем контекст для RAG-цепочки
            context_text = format_docs(
                docs
            )  # Ваша функция format_docs уже есть и отлично подходит

            # --- RAG-цепочка остается почти без изменений ---
            rag_chain = (
                {
                    "context": lambda x: context_text,  # Передаем уже найденный контекст
                    "question": RunnablePassthrough(),
                }
                | rag_prompt_template
                | llm
                | StrOutputParser()
            )

            # Получаем ответ от RAG-цепочки
            answer = rag_chain.invoke(user_query)

            # Выводим ответ LLM
            st.markdown("### 🧞‍♂️ Рекомендации от Джинна:")
            st.markdown(answer)

            # --- ИЗМЕНЕНИЕ 3: Отображаем "сырые" результаты с оценками ---
            st.markdown("---")
            st.markdown("### 🔹 Подробнее о сериалах:")

            # Теперь итерируемся по docs_with_scores, чтобы иметь доступ и к документу, и к оценке
            for d, score in docs_with_scores:
                with st.container(border=True):
                    cols = st.columns([1, 3])
                    with cols[0]:
                        if d.metadata.get("image_movie"):
                            st.image(
                                d.metadata["image_movie"], use_container_width=True
                            )
                    with cols[1]:
                        # Добавляем оценку прямо в заголовок
                        st.markdown(
                            f"#### {d.metadata.get('title', 'Без названия')} ⭐ КП: {d.metadata.get('film_rating_kp', 'Н/Д')} | ⭐ **IMDb:** {d.metadata.get('film_rating_imdb', 'Н/Д')} | ⭐ **KinoGo:** {d.metadata.get('rating_votes', 'Н/Д')}"
                        )
                        st.markdown(f"Степень соответствия: {score:.4f}")
                        st.markdown(
                            f"**Год:** {d.metadata.get('out_year', 'Н/Д')} | **Длительность:** {d.metadata.get('duration', 'Н/Д')}"
                        )
                        # ... остальная часть вашего кода для отображения метаданных ...
                        st.markdown(
                            f"**Жанры:** {', '.join(d.metadata.get('genres', []))}"
                        )
                        st.markdown(
                            f"**Страна:** {', '.join(d.metadata.get('country', []))}"
                        )
                        if d.metadata.get("url_movie"):
                            st.link_button(
                                "🔗 Смотреть на сайте", d.metadata.get("url_movie")
                            )

                        st.caption(f"Описание: *{d.page_content}*")
    else:
        st.warning("Пожалуйста, введи описание, чтобы я тебе помог✨")
