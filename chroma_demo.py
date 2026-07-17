import chromadb

# 改成持久化客户端，数据存在 ./chroma_data 文件夹
client = chromadb.PersistentClient(path="./chroma_data")

col = client.get_or_create_collection("test")

# 先判断有没有数据，没有就添加（避免重复添加报错）
if col.count() == 0:
    col.add(ids=["1"], documents=["hello world"])
    print("已存入数据")
else:
    print(f"已有 {col.count()} 条数据")

# 查询
result = col.query(query_texts=["hello"], n_results=1)
print(f"检索到：{result['documents'][0]}")