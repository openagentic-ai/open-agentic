# OpenAgentic

浼佷笟绾?AI Agent 骞冲彴 鈥?**Python锛團astAPI锛夊悗绔?* + **React 鍓嶇**锛岄潰鍚?**绉佹湁鍖?/ 鍐呯綉** 閮ㄧ讲锛氬ぇ妯″瀷瀵硅瘽浠?**闀挎湡鍦ㄧ嚎鏈嶅姟** 褰㈡€佽惤鍦ㄨ嚜鏈夊熀纭€璁炬柦锛涗細璇濅笌涓氬姟鏁版嵁杩?**鑷缓 PostgreSQL**锛涙ā鍨嬭皟鐢ㄩ€氳繃 **LiteLLM** 缁熶竴瀵规帴澶氬鍘傚晢銆傚 Agent銆佸伐鍏风紪鎺掋€丷AG銆佸伐浣滄祦绛夋寜 **Phase 璺嚎鍥?* 杩唬锛屽伐绋嬩笂棰勭暀 **鏉冮檺涓庡璁?* 鎵╁睍浣嶃€?

| 璧勬簮 | 閾炬帴 |
|------|------|
| **瀹樼綉** | [openagentic-ai.github.io](https://openagentic-ai.github.io) |
| **浠ｇ爜浠撳簱** | [github.com/openagentic-ai/open-agentic](https://github.com/openagentic-ai/open-agentic) |
| **璁稿彲璇?* | MIT |

---

## 鐩綍

- [褰撳墠瀹炵幇杩涘害锛堜笌浠撳簱浠ｇ爜涓€鑷达級](#褰撳墠瀹炵幇杩涘害涓庝粨搴撲唬鐮佷竴鑷?026-04-鏍稿)
- [椤圭洰鑳屾櫙涓庣洰鏍嘳(#椤圭洰鑳屾櫙涓庣洰鏍?
- [宸茶惤鍦拌兘鍔涗笌瀹炵幇鎵嬫锛堣杩帮紝涓冨皬鑺傦級](#宸茶惤鍦拌兘鍔涗笌瀹炵幇鎵嬫璇﹁堪涓冨皬鑺?
- [涓氬姟鍐呭涓庢ā鍧楄寖鍥碷(#涓氬姟鍐呭涓庢ā鍧楄寖鍥村凡瀹炵幇--瑙勫垝涓?
- [鎶€鏈ā鍧楄瑙ｏ紙鍗佸皬鑺傦級](#鎶€鏈ā鍧楄瑙ｆ槸浠€涔?-涓轰綍閫夊瀷--瑙ｅ喅浠€涔堥棶棰?
- [瑙勫垝鑳藉姏鎬昏锛圥hase 2鈥?锛塢(#瑙勫垝鑳藉姏鎬昏phase-26)
- [鎶€鏈爤鎬昏](#鎶€鏈爤鎬昏)
- [鏋舵瀯璁捐](#鏋舵瀯璁捐)锛堝惈閫昏緫绠€鍥俱€佸垎灞傝瑙ｃ€佷粨搴撶洰褰曪級
- [鏍稿績妯″潡涓?API 杈圭晫](#鏍稿績妯″潡涓?api-杈圭晫)
- [宸ョ▼鍖栦笌闈炲姛鑳介渶姹俔(#宸ョ▼鍖栦笌闈炲姛鑳介渶姹?
- [闅剧偣涓庡彇鑸峕(#闅剧偣涓庡彇鑸?
- [涓€娆℃祦寮忓璇濊姹傜殑瀹屾暣鐢熷懡鍛ㄦ湡](#涓€娆℃祦寮忓璇濊姹傜殑瀹屾暣鐢熷懡鍛ㄦ湡)
- [寮€鍙戣矾绾?Phase 0鈥?锛圱odo锛塢(#寮€鍙戣矾绾?phase-06todo)
- [蹇€熷惎鍔╙(#蹇€熷惎鍔?
- [CLI 妯″紡锛堢洿鎺ュ璇濓級](#cli-妯″紡鐩存帴瀵硅瘽)
- [API 绔偣](#api-绔偣)
- [鍓嶇 `ui/`](#鍓嶇-ui)
- [甯歌闂涓庢帓閿橾(#甯歌闂涓庢帓閿?
- [浠撳簱涓庤础鐚甝(#浠撳簱涓庤础鐚?
- [璁稿彲璇乚(#璁稿彲璇?

---

## 褰撳墠瀹炵幇杩涘害锛堜笌浠撳簱浠ｇ爜涓€鑷达紝2026-04 鏍稿锛?

> **璇存槑**锛氫笅鏂囥€岃杩般€嶇珷鑺備繚鐣?**璁捐鎰忓浘銆侀€夊瀷鐞嗙敱銆侀潰璇曞彲灞曞紑鍙ｅ緞**锛涙湰琛ㄤ笓闂ㄥ榻?**褰撳墠浠撳簱閲岀湡瀹炲啓浜嗕粈涔?*锛岄伩鍏嶇畝鍘嗕笌浠ｇ爜鑴辫妭銆備袱鑰?**骞跺瓨**锛氱煭琛ㄧ湅杩涘害锛岄暱鏂囩湅娣卞害銆?

| Phase | 鐘舵€?| 璇存槑 |
|-------|------|------|
| **Phase 0** | **鍩烘湰瀹屾垚** | FastAPI 宸ュ巶銆乣lifespan`銆丏ocker Compose锛?*`pgvector/pgvector:pg16`**锛夈€佸仴搴锋鏌ャ€乣core` 鐩綍涓庝緷璧栭摼銆?*`structlog` 宸叉帴鍏ュ惎鍔ㄦ棩蹇?*锛堣 `main.py`锛夈€?|
| **Phase 0 娉ㄦ剰椤?* | **宸插畬鎴?* | Alembic revision `62da57f49c3e_initial_tables` 宸茶ˉ榻愮敤鎴枫€佷細璇濄€佹秷鎭€丄gent 涓庢墽琛屽巻鍙茬瓑寤鸿〃閫昏緫锛涘紑鍙戠幆澧冧粛鐢?`create_all` 鍏滃簳锛岀敓浜х幆澧冭蛋 `alembic upgrade head`銆?|
| **Phase 1** | **宸插畬鎴?* | 娉ㄥ唽 / 鐧诲綍 / **JWT**銆佷細璇濅笌娑堟伅 **CRUD**銆?*LiteLLM** 璋冪敤銆?*SSE**锛坄StreamingResponse` + `text/event-stream`锛岃 `core/chat`锛夈€?*`ui/`** 鍓嶇涓?Phase 1 API 鍗忓悓銆?|
| **Phase 2** | **鍩虹鐗堝凡瀹屾垚** | 鏂板 `agent/` 涓?`mcp/` 瀹炵幇锛欰gent CRUD銆佹渶灏?ReAct 鎵ц鍣ㄣ€佸伐鍏锋敞鍐岃〃銆丮CP HTTP JSON-RPC 瀹㈡埛绔€佹墽琛屽巻鍙茶惤搴撲笌 API銆?|
| **Phase 3** | **宸插畬鎴?* | `workflow/` 宸插疄鐜帮細Workflow CRUD銆丷un 鎵ц涓庡彇娑堛€丏AG 鏍￠獙涓庢嫇鎵戞墽琛屻€佽妭鐐归噸璇?瓒呮椂銆佸彉閲忔ā鏉挎覆鏌撱€佽繍琛岃建杩逛笌鐘舵€佹煡璇€?|
| **Phase 4** | **鏈疄鐜帮紙鍗犱綅锛?* | `knowledge/` 鐩綍浠嶄负鍗犱綅锛涙暟鎹簱渚у凡閫?`pgvector` 闀滃儚锛屼负 RAG 钀藉湴鍋氬噯澶囥€?|
| **Phase 5** | **鏈疄鐜帮紙浠呴儴鍒嗗熀寤猴級** | 鏃犲畬鏁村绉熸埛璁¤垂闂幆銆佹棤 Prometheus **`/metrics`** 绛夛紱**`structlog` 宸叉帴鍏?* 涓嶇瓑浜庛€屽彲瑙傛祴鎬у叏濂椼€嶃€俙tenant/`銆乣observability/` 澶氫负鍗犱綅銆?|
| **Phase 6** | **閮ㄥ垎** | **`ui/`** 宸叉湁澶氶〉闈紙濡?Sessions銆丼ettings銆丼kills銆丆hannels銆丏evices 绛夛級锛汻EADME 甯歌鍒楃殑 **React Flow 宸ヤ綔娴佺紪杈戝櫒銆佺煡璇嗗簱绠＄悊 UI銆丄gent 妯℃澘甯傚満銆佺敓浜х骇 Nginx Compose 鎷撴墤** 绛?**灏氭湭涓?Phase 4/5 鍚庣鑳藉姏褰㈡垚闂幆**锛屼互浠ｇ爜涓哄噯銆?|

**涓庛€岃杩般€嶆鏂囩殑闃呰椤哄簭寤鸿**锛氬厛璇绘湰琛ㄥ缓绔?**浜嬪疄杈圭晫**锛屽啀璇?**銆屽凡钀藉湴鑳藉姏涓庡疄鐜版墜娈点€?* 涓?**銆屾妧鏈ā鍧楄瑙ｃ€?* 鐞嗚В **涓轰粈涔堣繖鏍疯璁°€佸悗缁€庝箞婕旇繘**銆?

---

## 椤圭洰鑳屾櫙涓庣洰鏍?

闈㈠悜浼佷笟 **绉佹湁鍖栭儴缃?* 鍦烘櫙锛氬皢澶фā鍨嬪璇濅互 **鍙暱鏈熷湪绾跨殑鏈嶅姟褰㈡€?* 閮ㄧ讲鍦ㄨ嚜鏈夋湇鍔″櫒涓庡唴缃戯紝瑕嗙洊 **瀹㈡湇銆佽窡鍗曘€佸埗搴︿笌鍐呴儴鐭ヨ瘑搴撻棶绛?* 绛夊父瑙佷笟鍔°€傛牳蹇冧骇鍝佺洰鏍囨槸 **瀹夊叏鍙帶** 鈥斺€?涓氬姟鏁版嵁涓庢ā鍨嬭皟鐢ㄨ竟鐣岀暀鍦ㄤ紒涓氫晶锛岄檷浣庡皢鏍稿績涓氬姟鏁版嵁澶栨硠鍒板叕缃?SaaS 鐨勯闄┿€?

褰撳墠闃舵宸茶惤鍦?**缁熶竴璐﹀彿銆佸浼氳瘽绠＄悊**銆佸鎺?**100+ 鍘傚晢妯″瀷** 鐨?**娴佸紡瀵硅瘽**锛堥€氳繃 LiteLLM 缁熶竴缃戝叧锛夛紝浼氳瘽涓庝笟鍔℃暟鎹啓鍏?**鑷缓 PostgreSQL**锛涘 Agent 鍗忓悓銆佸伐鍏风紪鎺掑強鍩轰簬涓氬姟鏁版嵁鐨勬寔缁紭鍖栨寜 **浜у搧璺嚎鍥?* 杩唬锛屽苟鍦ㄥ伐绋嬩笂棰勭暀 **鏉冮檺鎺у埗涓庢搷浣滃璁?* 绛夋不鐞嗚姹傘€?

**涓庡疄鐜扮殑瀵瑰簲鍏崇郴**锛氥€岃处鍙?/ 澶氫細璇?/ 澶氬巶鍟嗘祦寮?/ 鑷缓搴撱€嶅垎鍒敱 **JWT + bcrypt銆丆onversation/Message REST銆丩iteLLM + SSE銆丳ostgres + Compose +锛圓lembic 鎴栧紑鍙戞€?create_all锛?* 绛夌粍鍚堣惤鍦帮紱璺嚎鍥句笌娌荤悊棰勭暀鐨?**宸ョ▼钀界偣** 瑙佷笅鏂?**銆屽凡钀藉湴鑳藉姏涓庡疄鐜版墜娈碉紙璇﹁堪锛夈€?*锛堝垎 7 涓皬鑺傦紝鍚姹傞摼銆佽祫婧愭ā鍨嬨€佹祦寮忓舰鎬併€佽縼绉讳笌瀹¤鎵╁睍浣嶏級銆?

---

## 宸茶惤鍦拌兘鍔涗笌瀹炵幇鎵嬫锛堣杩帮紝涓冨皬鑺傦級

浠ヤ笅涓?[open-agentic](https://github.com/openagentic-ai/open-agentic) 鍏紑浠撳簱鍙婂吀鍨?**FastAPI + LiteLLM** 钀藉湴鏂瑰紡瀵归綈锛涜嫢浣犳湰鍦板垎鏀湁棰濆涓棿浠讹紝浠ヤ唬鐮佷负鍑嗐€?

### 1锛夌粺涓€璐﹀彿锛氫粠娉ㄥ唽鍒般€屽甫韬唤璋冪敤 API銆?

**鎺ュ彛涓庢暟鎹祦**

- **娉ㄥ唽**锛氬鎴风 `POST /api/auth/register` 鎻愪氦鐢ㄦ埛鍚嶃€佸瘑鐮佺瓑锛堝叿浣撳瓧娈典互 OpenAPI `/docs` 涓哄噯锛夈€傛湇鍔＄瀵瑰瘑鐮佸仛 **bcrypt** 鍝堝笇锛堜笉瀛樻槑鏂囷級锛屽皢鐢ㄦ埛琛屽啓鍏?**PostgreSQL**锛圫QLAlchemy 妯″瀷锛?*鐢熶骇鐜**浠?**Alembic revision** 淇濊瘉鍚勭幆澧冭〃缁撴瀯涓€鑷达紝瑙佷笂鏂囥€孭hase 0 娉ㄦ剰椤广€嶏級銆?
- **鐧诲綍**锛歚POST /api/auth/login` 鏍￠獙鐢ㄦ埛鍚嶅瘑鐮侊紱鏍￠獙閫氳繃鍚庝娇鐢?**python-jose** 鎸夐厤缃殑 **绛惧悕绠楁硶涓庡瘑閽?* 绛惧彂 **Access Token**锛堝強鎸夐渶鐨?**Refresh Token** 绛栫暐锛夈€侸WT 杞借嵎涓嚦灏戝寘鍚?**`sub`锛堢敤鎴蜂富閿垨绋冲畾鏍囪瘑锛?*銆乣exp`锛堣繃鏈熸椂闂达級绛夋爣鍑嗗０鏄庯紝渚夸簬鍚庣画鎵€鏈夊彈淇濇姢璺敱 **鏃犵姸鎬?* 楠岀銆?
- **鍒锋柊**锛歚POST /api/auth/refresh` 鍦?**婊戝姩浼氳瘽** 鎴?**鍙屼护鐗?* 绛栫暐涓嬪欢闀垮彲鐢ㄦ椂闂达紙瀹炵幇缁嗚妭浠ヤ粨搴撲负鍑嗭級锛屽噺灏戠敤鎴峰弽澶嶈緭瀵嗙爜銆?
- **褰撳墠鐢ㄦ埛**锛歚GET /api/auth/me` 閫氳繃 FastAPI **渚濊禆娉ㄥ叆** 浠?`Authorization: Bearer` 瑙ｆ瀽 JWT锛屽け璐ュ垯 **401**锛涙垚鍔熷垯杩斿洖鐢ㄦ埛妗ｆ锛屼緵鍓嶇灞曠ず鏄电О銆佸ご鍍忔墿灞曚綅绛夈€?

**宸ョ▼涓婅В鍐充粈涔堥棶棰?*

- **澶氱鎴蜂箣鍓嶇殑銆屽崟绉熸埛澶氱敤鎴枫€?*锛氬厛淇濊瘉 **浜?* 涓?**鏁版嵁** 缁戝畾锛屽悗缁啀鍙犵粍缁?/ 瑙掕壊涓嶄細鎺ㄧ炕璐﹀彿妯″瀷銆?
- **姘村钩鎵╁睍**锛氭棤浼氳瘽绮樻粸鍦ㄥ崟鏈哄唴瀛橈紝API 瀹炰緥鍙鍙伴儴缃诧紙闇€鍏变韩鍚屼竴楠岀瀵嗛挜鎴栦娇鐢ㄩ潪瀵圭О JWT + JWKS 婕旇繘锛夈€?
- **瀹夊叏鍩虹嚎**锛氬瘑鐮佸搱甯屻€丠TTPS锛堥儴缃插眰锛夈€佸瘑閽ヤ笉杩涗粨搴擄紝婊¤冻鍐呯綉浜や粯鐨?**鏈€浣庡畨鍏ㄥ彊浜?*銆?

### 2锛夊浼氳瘽绠＄悊锛歊EST 璧勬簮妯″瀷 + 寮傛钀藉簱

**璧勬簮鍒掑垎**

- **Conversation锛堝璇濓級**锛氫竴绾ц祫婧愶紝`GET /api/conversations` 鍒嗛〉 / 鍒楄〃锛堝叿浣撳垎椤靛弬鏁颁互浠ｇ爜涓哄噯锛夈€乣POST` 鍒涘缓銆乣GET /api/conversations/{id}` 鍙栬鎯呫€乣DELETE` 鍒犻櫎銆傛瘡鏉′細璇濆湪搴撲腑甯︽湁 **鎵€鏈夎€?`user_id`锛堝閿級**銆佹爣棰樸€佹椂闂存埑绛夛紝淇濊瘉 **鍙兘鎿嶄綔鑷繁鐨勪細璇?*锛堝湪璺敱鎴?service 灞傝繃婊わ級銆?
- **Message锛堟秷鎭級**锛氫簩绾ц祫婧愶紝鎸傚湪鏌?`conversation_id` 涓嬶細`GET 鈥?conversations/{id}/messages` 鎷夊巻鍙诧紱`POST 鈥?messages` **鍙戦€佹柊娑堟伅骞惰Е鍙戞ā鍨?*銆傝繖鏍峰墠绔彲浠?**浼氳瘽鍒楄〃 鈫?鐐硅繘浼氳瘽 鈫?娑堟伅鏃堕棿绾?* 鐨勪骇鍝佺粨鏋勶紝涓?Slack / ChatGPT 绫?UX 涓€鑷淬€?

**鎸佷箙鍖栦笌涓€鑷存€?*

- 鎵€鏈夎鍐欑粡 **AsyncSession**锛氬湪 `async def` 璺敱閲?`await session.commit()` / `rollback()`锛岄伩鍏嶉樆濉炰簨浠跺惊鐜€?
- **鍒犻櫎浼氳瘽**鏃跺簲鍦ㄥ悓涓€浜嬪姟鍐?**绾ц仈鍒犻櫎娑堟伅**锛堟垨杞垹闄わ級锛岄槻姝㈠鍎挎秷鎭崰绌洪棿銆佹硠闇插巻鍙层€?
- 涓哄悗缁?**瀹¤** 棰勭暀锛氭秷鎭〃鍙墿灞?**role锛坲ser / assistant / system锛?*銆?*token_usage JSON**銆?*model_name** 绛夊垪锛屼究浜庢寜浼氳瘽缁熻鎴愭湰涓庡洖鏀俱€?

**瑙ｅ喅浠€涔堥棶棰?*

- **銆屽彧鏈変竴涓叏灞€鑱婂ぉ绐椼€?*锛氫紒涓氬満鏅渶瑕?**鎸夊鎴?/ 鎸夊伐鍗?/ 鎸変富棰?* 鎷嗙嚎绋嬶紱浼氳瘽妯″瀷鏄悗缁?**鏉冮檺鎸変細璇濄€佸鍑烘寜浼氳瘽** 鐨勫墠鎻愩€?
- **鍙拷婧?*锛氬嚭闂鏃跺彲浠?**鎸?`conversation_id`** 鎷夊叏閾捐矾娑堟伅涓庡綋鏃堕€夌敤鐨勬ā鍨嬨€?

### 3锛?00+ 鍘傚晢妯″瀷锛歀iteLLM 浣滀负缁熶竴缃戝叧灞?

**瀹炵幇鎬濊矾**

- 鍦?**`core/llm`**锛堢洰褰曞悕浠ヤ粨搴撲负鍑嗭級灏佽瀵?**LiteLLM** 鐨勮皟鐢細涓婂眰鍙紶 **妯″瀷鏍囪瘑瀛楃涓?*銆?*messages**銆佹槸鍚?**stream** 绛夛紝涓嶅叧蹇冨簳灞傛槸 OpenAI銆丄zure銆丄nthropic 鍏煎绔繕鏄浗鍐呭巶鍟嗗吋瀹圭銆?
- **妯″瀷鍙戠幇**锛歚GET /api/models` 灏嗐€屽綋鍓嶇幆澧冨彲鐢ㄧ殑妯″瀷鍒楄〃銆嶆毚闇茬粰鍓嶇涓嬫媺妗嗭紱鍒楄〃鏉ユ簮鍙互鏄?LiteLLM 閰嶇疆銆侀潤鎬佺櫧鍚嶅崟鎴?**鍔ㄦ€佹帰娴?*锛堜互瀹為檯瀹炵幇涓哄噯锛夈€?
- **瀵嗛挜涓庤矾鐢?*锛氬悇鍘傚晢 **API Key銆乥ase_url** 鏀惧湪 **鐜鍙橀噺鎴栧鎴峰瘑閽ョ鐞嗙郴缁?*锛岀敱 Pydantic Settings 娉ㄥ叆锛涢伩鍏嶆妸瀵嗛挜鍐欒繘鍓嶇鎴栭暅鍍忓眰锛堥櫎闈炴瀯寤哄弬鏁扮敱 CI 娉ㄥ叆涓旈暅鍍忕鏈夛級銆?

**瑙ｅ喅浠€涔堥棶棰?*

- **瀵规帴杈归檯鎴愭湰**锛氭柊鍘傚晢寰€寰€鏄?**鍔犻厤缃€岄潪鍔犲垎鏀?*锛岀鍚堝钩鍙板瀷浜у搧鑺傚銆?
- **鏁呴殰闅旂**锛氱綉鍏冲眰鍙粺涓€ **瓒呮椂銆侀噸璇曘€侀檷绾?*锛堜緥濡備富妯″瀷澶辫触鍥為€€鍒板鐢ㄥ皬妯″瀷 鈥斺€?绛栫暐鍙凯浠ｏ級銆?
- **鏈潵璁¤垂**锛氬湪缃戝叧缁熻 **姣忔璋冪敤鐨?input / output tokens** 鍐欏叆琛ㄦ垨鏃ュ織锛屼负 Phase 5 **鎸夐噺璁¤垂** 鍩嬬偣銆?

### 4锛夋祦寮忓璇濓細SSE + 寮傛鐢熸垚鍣?

**鍗忚涓庝綋楠?*

- **SSE**锛歚POST 鈥?conversations/{id}/messages` 杩斿洖 `Content-Type: text/event-stream`锛堟垨妗嗘灦绛変环鐗╋級锛屾鏂囦负 **浜嬩欢娴?*锛氭瘡涓?**delta** 鎼哄甫妯″瀷鏂板鏂囨湰鐗囨锛屽墠绔敤 **EventSource** 鎴?`fetch` ReadableStream 娑堣垂銆?
- **鍚庣褰㈡€?*锛欶astAPI 渚ч€氬父杩斿洖 **`StreamingResponse`**锛屽唴閮?**`async for chunk in llm_astream(...): yield format_sse(chunk)`**锛屾妸 LiteLLM 鐨?**寮傛娴?* 妗ュ埌 HTTP銆?
- **涓?JWT 缁撳悎**锛氬湪 **寤虹珛娴佷箣鍓?* 瀹屾垚閴存潈锛涙祦涓€斿鎴风鏂紑鏃跺簲 **鍙栨秷涓婃父鐢熸垚**锛坄asyncio.CancelledError` 澶勭悊锛夛紝閬垮厤鐧界櫧娑堣€?token銆?

**瑙ｅ喅浠€涔堥棶棰?*

- **棣栧瓧寤惰繜锛圱TFB锛?*锛氶暱鍥炵瓟涓嶅繀绛夊叏鏂囩敓鎴愬畬鎵嶈繑鍥烇紝鏄捐憲鏀瑰杽 **浣撴劅閫熷害**銆?
- **寮辩綉鍦烘櫙**锛氱敤鎴峰彲鏇存棭鐪嬪埌閮ㄥ垎杈撳嚭锛屽噺灏戙€屽崱姝婚噸璇曘€嶃€?

### 5锛変細璇濅笌涓氬姟鏁版嵁鍐欏叆鑷缓 PostgreSQL

**閮ㄧ讲鎷撴墤**

- **Docker Compose** 涓畾涔?**postgres** 鏈嶅姟锛堥暅鍍忕増鏈拤姝讳负 **16** 鎴栧鎴疯鍙増鏈級銆?*鏁版嵁鍗?* 鎸佷箙鍖?`/var/lib/postgresql/data`锛屽簲鐢ㄦ湇鍔￠€氳繃 **鏈嶅姟鍚?DNS** 璁块棶 `DATABASE_URL`銆?
- 搴旂敤闀滃儚鎴栨湰鍦拌繘绋嬮€氳繃 **`postgresql+asyncpg://...`** 杩炴帴锛?*杩炴帴姹?* 鍦?lifespan 涓垱寤恒€佸湪 shutdown 涓叧闂€?

**Schema 涓庤縼绉?*

- **Alembic**锛氭瘡娆℃敼 ORM 妯″瀷鍚庣敓鎴?revision锛宍upgrade` 搴旂敤鍒板悇鐜锛涚敓浜у彉鏇磋蛋 **璇勫 + 澶囦唤 + 绐楀彛**銆?
- **pgvector**锛氫互鎵╁睍褰㈠紡 `CREATE EXTENSION IF NOT EXISTS vector`锛堝叿浣撹縼绉昏剼鏈互浠撳簱涓哄噯锛夛紝涓?Phase 4 **鍚戦噺鍒?/ 鍚戦噺琛?* 棰勭暀銆?

**瑙ｅ喅浠€涔堥棶棰?*

- **鏁版嵁涓绘潈**锛氬璇濅笌涓氬姟 **涓嶅嚭瀹㈡埛鍐呯綉**锛堟ā鍨嬭皟鐢ㄨ嫢璧板叕缃?API 鍒欏彟绛惧悎瑙勶紝涓庡簱鍒嗙璁ㄨ锛夈€?
- **鍙仮澶?*锛氬浠芥仮澶嶆紨缁冩湁鏄庣‘瀵硅薄锛圥G 瀹炰緥锛夈€?
- **鍙紨杩?*锛氫粠銆屽彧瀛樻秷鎭枃鏈€嶆紨杩涘埌銆屽瓨 embedding銆佸瓨 usage銆嶄笉鎺ㄧ炕瀛樺偍閫夊瀷銆?

### 6锛夎矾绾垮浘鑳藉姏锛堝 Agent銆佸伐鍏风紪鎺掋€佹寔缁紭鍖栵級锛氭ā鍧楀寲棰勭暀

**浠ｇ爜涓庢枃妗ｅ榻?*

- 浠撳簱 `src/openagentic/` 涓嬪凡鎷嗗垎 **`agent/`銆乣workflow/`銆乣knowledge/`銆乣mcp/`** 绛夊寘锛屼笌 README **Phase 2鈥?** 涓€涓€瀵瑰簲锛?
  - **Phase 2**锛欰gent CRUD銆?*ReAct 寰幆**銆佸伐鍏锋敞鍐岃〃銆?*MCP Client**銆佹墽琛屽巻鍙层€?
  - **Phase 3**锛欽SON **DAG**銆佹嫇鎵戞帓搴忔墽琛屻€佽妭鐐归棿 **`{{var}}` 妯℃澘浼犲弬**銆?
  - **Phase 4**锛氭枃妗ｄ笂浼犮€佸垎鍧椼€佸祵鍏ャ€?*pgvector** 妫€绱€佷笌 Agent / 宸ヤ綔娴侀泦鎴愩€?
- **褰撳墠鏈疄鐜扮殑鎺ュ彛**锛堝閮ㄥ垎 `GET /api/agents` 绛夛級鍦?README 涓瘹瀹炴爣娉?**寰呭疄鐜?/ 鍗犱綅**锛岄伩鍏嶈繃搴︽壙璇猴紱闈㈣瘯鏃跺彲寮鸿皟 **銆屽厛搴曞骇鍚庢櫤鑳戒綋銆?* 鐨勪氦浠橀『搴忋€?

**瑙ｅ喅浠€涔堥棶棰?*

- **閬垮厤宸ㄧ煶绫诲悕娣蜂贡**锛氬垎鍖呭嵆 **闄愮晫涓婁笅鏂?* 闆忓舰銆?
- **闄嶄綆鍚庣画闆嗘垚 MCP 鐨勬垚鏈?*锛氬崗璁笌鐩綍浣嶅凡鐣欙紝鍑忓皯浠?0 寮曞叆 MCP 鏃剁殑鐩綍澶ф尓绉汇€?

### 7锛夋潈闄愭帶鍒朵笌鎿嶄綔瀹¤锛氬伐绋嬮鐣欑殑鍏蜂綋钀界偣

**褰撳墠鍙仛鐨勩€屼笉鎺ㄧ炕寮忋€嶉鐣?*

- **鏁版嵁鎵€鏈夋潈**锛氫細璇濄€佹秷鎭〃寮哄埗 **`user_id`**锛屾墍鏈夋煡璇㈤粯璁ゅ甫 **`WHERE user_id = current_user`**锛屼负鍚庣画 **RBAC** 鍙犲姞 **缁勭粐 ID** 鐣?JOIN 浣嶃€?
- **JWT 澹版槑鎵╁睍**锛氶鐣欒嚜瀹氫箟 claims锛堝 `org_id`銆乣role`锛夌殑瑙ｆ瀽涓庢牎楠屽嚱鏁帮紝鍗充娇鏆傛椂涓嶇鍙戯紝涔熶笉鍦ㄤ唬鐮侀噷鍐欐銆屽彧鏈?sub銆嶃€?
- **瀹¤涓庤娴嬶紙Phase 5锛?*锛氳矾绾夸腑鍖呭惈 **structlog銆乧orrelation ID銆丳rometheus**锛涘疄鐜颁笂鍙湪涓棿浠舵敞鍏?**request_id**锛屽湪姣忔 LLM 璋冪敤鍓嶅悗鎵?**缁撴瀯鍖栨棩蹇?*锛堢敤鎴枫€佷細璇濄€佹ā鍨嬨€佽€楁椂銆乼oken锛屾敞鎰?**鑴辨晱**锛夈€?

**瑙ｅ喅浠€涔堥棶棰?*

- **绛変繚 / 鍐呭闂瓟**锛氳兘璇存竻 **璋佸湪浣曟椂璁块棶浜嗗摢绫绘暟鎹?*锛岃€屼笉鏄€屽彧鏈?nginx access log銆嶃€?
- **浜嬫晠褰掑洜**锛氬嚭鐜拌秺鏉冩垨璇皟鐢ㄦ椂锛屾湁 **浼氳瘽绾?* 涓?**璇锋眰绾?* 绾跨储銆?

---

## 涓氬姟鍐呭涓庢ā鍧楄寖鍥达紙宸插疄鐜?/ 瑙勫垝涓級

**宸插疄鐜帮紙涓?Phase 0鈥? 瀵归綈锛岀粏鑺備互浠ｇ爜涓哄噯锛?*

- 搴旂敤鑴氭墜鏋讹細FastAPI 搴旂敤宸ュ巶銆佺敓鍛藉懆鏈熺鐞嗐€佸仴搴锋鏌ャ€?
- 鏁版嵁灞傦細PostgreSQL 16 + **pgvector 闀滃儚**锛堝叧绯绘暟鎹笌鍚戦噺鎵╁睍涓€浣撳寲锛夈€丼QLAlchemy **2.0 寮傛** ORM銆?*Alembic 宸ョ▼**锛坮evision 闇€鎸夌幆澧冪淮鎶わ級銆?*Pydantic Settings** 闆嗕腑閰嶇疆銆?
- 璁よ瘉锛?*娉ㄥ唽 / 鐧诲綍 / JWT锛坧ython-jose锛? bcrypt**锛涘璇?**CRUD**銆?
- LLM锛?*LiteLLM** 缁熶竴缃戝叧锛屽鎺?**100+ Provider**锛涘璇?**SSE 娴佸紡** 杩斿洖銆?
- 鍓嶇锛?*React + Vite + TailwindCSS + Zustand** 绠＄悊绔笌瀵硅瘽鐣岄潰锛屼笌鍚庣 **REST + SSE** 鍗忎綔銆?
- 浜や粯锛歚docker compose` 鎷夎捣搴旂敤涓庢暟鎹簱锛堝惈 **depends_on** 涓?Postgres **healthcheck**锛夛紝渚夸簬鍐呯綉涓€閿媺璧枫€?

---

## 鎶€鏈ā鍧楄瑙ｏ紙鏄粈涔?路 涓轰綍閫夊瀷 路 瑙ｅ喅浠€涔堥棶棰橈級

浠ヤ笅涓?OpenAgentic **宸插疄鐜伴樁娈?*鍚勬妧鏈ā鍧楃殑璇存槑锛屼究浜庨潰璇曞睍寮€涓庢灦鏋勮瘎瀹″榻愩€?

### 1锛塅astAPI锛氬簲鐢ㄥ伐鍘傘€佺敓鍛藉懆鏈熶笌鍋ュ悍妫€鏌?

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **FastAPI**锛氬熀浜?Python 绫诲瀷鎻愮ず鐨?**ASGI Web 妗嗘灦**锛岃嚜鍔ㄧ敓鎴?**OpenAPI锛圫wagger锛?* 鏂囨。锛屽師鐢熸敮鎸?**寮傛** 璺敱涓庝緷璧栨敞鍏ャ€?
- **搴旂敤宸ュ巶**锛氱敤鍑芥暟锛堝 `create_app()`锛夊垱寤?`FastAPI` 瀹炰緥锛屼究浜庢寜鐜锛堝紑鍙?/ 娴嬭瘯 / 鐢熶骇锛夋寕杞戒笉鍚屼腑闂翠欢銆佽矾鐢辨垨 Mock銆?
- **鐢熷懡鍛ㄦ湡锛坙ifespan锛?*锛氬湪搴旂敤鍚姩鏃跺缓绔?**鍏ㄥ眬璧勬簮**锛堝鏁版嵁搴撹繛鎺ユ睜锛夛紝鍦ㄥ叧闂椂 **浼橀泤閲婃斁**锛岄伩鍏嶈繛鎺ユ硠婕忋€?
- **鍋ュ悍妫€鏌ワ紙濡?`GET /health`锛?*锛氱粰 **璐熻浇鍧囪　銆並8s probe銆佽繍缁磋剼鏈?* 涓€涓交閲忕鐐癸紝鍒ゆ柇杩涚▼鏄惁瀛樻椿銆佷緷璧栵紙濡?DB锛夋槸鍚﹀彲杈俱€?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- 绉佹湁鍖栧満鏅渶瑕?**鑷墭绠?HTTP API**锛孎astAPI 鍦?**寮傛 I/O**銆?*鑷姩鏂囨。**銆?*Pydantic 鏍￠獙** 涓婁笌椤圭洰鎶€鏈爤涓€鑷达紝瀛︿範鏇茬嚎瀵圭啛鎮?Python 鐨勫洟闃熷弸濂姐€?
- 搴旂敤宸ュ巶 + lifespan 鏄?**12-factor** 涓庡彲娴嬭瘯鎬х殑甯歌鍐欐硶锛屽悗缁帴 **澶?Worker銆佺伆搴?* 鏃朵笉鑷充簬鎶婂垵濮嬪寲閫昏緫鍐欐鍦ㄦā鍧?import 鍓綔鐢ㄩ噷銆?

**鑳借В鍐充粈涔堥棶棰?*

- **鍚姩鏈夊簭**锛氬厛杩炲簱鍐嶆敹娴侀噺锛岄伩鍏嶃€屾湇鍔″凡鐩戝惉浣嗕竴鏌ュ簱灏辩偢銆嶇殑绔炴€併€?
- **杩愮淮鍙娴?*锛氭帰娲讳笌缂栨帓绯荤粺闆嗘垚锛屽揩閫熶粠銆?02銆嶉噷鍖哄垎 **杩涚▼鎸備簡** 杩樻槸 **涓嬫父 DB 鎸備簡**銆?
- **鍥㈤槦鍗忎綔**锛歋wagger 闄嶄綆鍓嶅悗绔?**濂戠害娌熼€氭垚鏈?*銆?

### 2锛塒ostgreSQL 16

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **PostgreSQL**锛氬紑婧?**鍏崇郴鍨嬫暟鎹簱绠＄悊绯荤粺锛圧DBMS锛?*锛岀敤 **SQL** 绠＄悊鏁版嵁锛涙彁渚?**ACID 浜嬪姟**銆佽〃 / 绾︽潫 / 澶栭敭銆佸绉?**绱㈠紩**锛圔-tree銆丟IN銆丟iST 绛夛級銆?*JSONB**銆?*鍏ㄦ枃妫€绱?*銆佺獥鍙ｅ嚱鏁般€丆TE 绛変紒涓氬父鐢ㄨ兘鍔涖€?
- **鍦ㄦ湰椤圭洰涓殑鐢ㄩ€?*锛氫綔涓?**涓绘寔涔呭寲寮曟搸**锛屽瓨鏀?**鐢ㄦ埛銆佷細璇濄€佹秷鎭?* 绛変笟鍔¤〃锛涘悗缁叾浠栫壒鎬э紙濡傚璁″瓧娈点€佸绉熸埛缁勭粐琛級浠嶅湪鍚屼竴濂楀簱鍐呮紨杩涖€?
- **PostgreSQL 16**锛氶€夌敤杈冩柊澶х増鏈紝鍦?**鏌ヨ浼樺寲鍣ㄣ€佺洃鎺т笌杩愮淮宸ュ叿閾?* 涓婄浉瀵规洿鎴愮啛锛涘鎴疯嫢鍥哄畾鍩虹嚎鍙啀閽夊皬鐗堟湰鍙枫€?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- **绉佹湁鍖栦笌鍚堣**锛氬唴缃戦儴缃叉椂瀹㈡埛鏇村叧蹇?**鏁版嵁钀界偣銆佸浠芥仮澶嶃€佹潈闄愭ā鍨?*锛汸ostgreSQL 鐢熸€佹垚鐔燂紝**DBA 涓庣瓑淇濇潗鏂?*閲屽彲瑙ｉ噴鎬у己銆?
- **涓?Python 鍚庣鏍堝鍚?*锛氫笌 **SQLAlchemy 2.0 + Alembic + asyncpg** 缁勫悎涓轰簨瀹炴爣鍑嗕箣涓€锛岄檷浣庨暱鏈熺淮鎶ょ殑銆屽喎闂ㄦ爤銆嶉闄┿€?
- **鍙墿灞曡€岄潪鎹骇鍝?*锛氬悜閲忚兘鍔涢€氳繃 **鎵╁睍锛堣涓嬩竴鑺?pgvector锛?* 鍙犲姞锛屾棤闇€涓?RAG 鍗曠嫭寮曞叆鍙︿竴濂楁暟鎹簱鍝佺墝锛?*閲囪喘涓庤繍缁磋竟鐣?*鏇寸畝鍗曘€?

**鑳借В鍐充粈涔堥棶棰?*

- **寮轰竴鑷翠笟鍔℃暟鎹?*锛氫細璇濅笌娑堟伅鐨勫啓鍏ャ€佸垹闄ゃ€佹煡璇㈠湪 **鍗曞簱浜嬪姟** 鍐呭畬鎴愶紝閬垮厤銆屽璇濆湪缂撳瓨閲屻€佽惤搴撳け璐ョ敤鎴蜂笉鐭ラ亾銆嶇被闂銆?
- **澶囦唤涓庡鐏?*锛氭部鐢ㄦ垚鐔熺殑 **pg_dump / 涓讳粠 / PITR** 绛夋柟妗堬紝婊¤冻浼佷笟 **RPO / RTO** 璁ㄨ妗嗘灦銆?
- **澶嶆潅鏌ヨ涓庢紨杩?*锛氭潈闄愩€佺粺璁°€佽繍钀ユ姤琛ㄧ瓑鍚庣画闇€姹傚彲鐢?**鏍囧噯 SQL + 绱㈠紩** 瑙ｅ喅锛屼笉杩囨棭缁戞涓撶敤瀛樺偍銆?

### 3锛塸gvector 鎵╁睍

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **pgvector**锛氬畨瑁呭湪 PostgreSQL 涓婄殑 **鎵╁睍锛坋xtension锛?*锛屾彁渚?**`vector` 绫诲瀷** 鍙?**璺濈 / 杩戦偦鏌ヨ** 鑳藉姏锛堝娆ф皬銆佷綑寮︺€佸唴绉瓑璇箟锛屼互鎵╁睍涓庣増鏈枃妗ｄ负鍑嗭級锛屽苟鏀寔 **鍚戦噺绱㈠紩**锛堝 **IVFFlat銆丠NSW** 绛夛紝瑙?PG 涓庢墿灞曠増鏈€屽畾锛夛紝鐢ㄤ簬瀵?**embedding 鍚戦噺** 鍋?**鐩镐技搴︽绱?*銆?
- **鍦ㄦ湰椤圭洰涓殑鐢ㄩ€?*锛氫笌 README **Phase 4锛堢煡璇嗗簱 / RAG锛?* 瀵归綈 鈥斺€?灏?**鏂囨。鍧楀悜閲?* 涓?**鏉ユ簮 metadata** 瀛樺湪搴撳唴锛屼笌 **鐢ㄦ埛 / 浼氳瘽 / 鐭ヨ瘑搴?* 绛夊叧绯绘暟鎹?**鍚屽疄渚嬪叧鑱?*锛涘綋鍓嶉樁娈靛彲涓?schema **棰勭暀鍒楁垨鐙珛琛?*锛岄€愭涓婄嚎妫€绱㈤摼璺€?
- **涓庛€屽彧鐢?PostgreSQL銆嶇殑鍏崇郴**锛氬畠 **涓嶆敼鍙?* PostgreSQL 浣滀负鍏崇郴搴撶殑鏈川锛屽彧鏄湪鍚屼竴杩涚▼鍐?**澧炲姞涓€绉嶆暟鎹被鍨嬩笌绠楀瓙**锛岀敱 `CREATE EXTENSION vector` 鍚敤銆?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- **涓庝笟鍔″簱鍚屼簨鍔°€佸悓杩炴帴**锛氭绱㈢粨鏋滃彲涓?**绉熸埛 / ACL / 鏂囨。鐗堟湰** 绛夋潯浠?**鍦ㄥ悓涓€鏉?SQL 鎴栧悓涓€浜嬪姟** 涓繃婊わ紝鍑忓皯銆屽悜閲忓簱涓庝笟鍔″簱鏁版嵁涓嶄竴鑷淬€嶇殑鍚屾闅鹃銆?
- **杩愮淮缁勪欢鏁板皯**锛氬浠姐€佺洃鎺с€佸憡璀︿粛涓昏鍥寸粫 **PostgreSQL**锛涚浉瀵广€屼笓鐢ㄥ悜閲忔暟鎹簱 + 涓氬姟搴撱€嶅弻鏍堬紝**鍐呯綉闃茬伀澧欑瓥鐣ヤ笌鎴愭湰璇存槑** 鏇寸洿瑙傘€?
- **璺嚎涓庝骇鍝佷竴鑷?*锛氫骇鍝佽鍒掓槑纭?**pgvector 瀛樺祵鍏?*锛涘厛閫夊畾鎵╁睍璺緞锛岄伩鍏嶅厛鍋氫竴濂?Chroma / Milvus 鍐?**鏁翠綋鎼縼鍚戦噺瀛樺偍** 鐨勯噸杩佺Щ銆?

**鑳借В鍐充粈涔堥棶棰?*

- **RAG 杩戦偦妫€绱?*锛氭寜 query embedding 鍙?**Top-K 鏂囨。鍧?*锛屼緵 LLM **鏈変緷鎹敓鎴?*銆?
- **甯︾害鏉熺殑璇箟妫€绱?*锛氫緥濡傘€屼粎鍦ㄦ煇鐢ㄦ埛鍙鐨勭煡璇嗗簱闆嗗悎鍐呭仛鍚戦噺妫€绱€嶏紝鐢?**澶栭敭 + WHERE** 涓庡悜閲忔帓搴忕粍鍚堝畬鎴愩€?
- **璇佹嵁閾句笌鐗堟湰**锛氬悜閲忎笌 **chunk_id銆佹枃浠剁増鏈彿** 鍚屽瓨锛屼究浜?**閲嶅缓绱㈠紩銆佸洖鏀捐瘎娴?* 鏃跺榻愩€屽綋鏃剁敤鐨勫摢鐗堟潗鏂欍€嶃€?

### 4锛塖QLAlchemy 2.0 寮傛 ORM 涓?asyncpg

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **SQLAlchemy 2.0**锛歅ython 鐢熸€佷富娴佺殑 **ORM / SQL 宸ュ叿鍖?*锛?.x 椋庢牸缁熶竴浜?**Core 涓?ORM**锛屽苟涓€绛夋敮鎸?**寮傛锛圓syncSession锛?*銆?
- **寮傛 ORM**锛氳矾鐢变笌鏁版嵁搴?I/O 浣跨敤 `async` / `await`锛屽湪绛夊緟鏁版嵁搴撳搷搴旀椂 **涓嶉樆濉炰簨浠跺惊鐜?*锛屽彲骞跺彂澶勭悊鏇村璇锋眰銆?
- **asyncpg**锛氶珮鎬ц兘 **寮傛 PostgreSQL 椹卞姩**锛屽父涓?`postgresql+asyncpg` 杩炴帴涓查厤鍚?SQLAlchemy 浣跨敤銆?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- 椤圭洰鍚屾椂瀛樺湪 **REST 鐭姹?* 涓?**SSE 闀胯繛鎺?*锛涘紓姝ユ爤閬垮厤銆屼竴涓參鏌ヨ鎷栦綇鏁磋繘绋嬨€嶇殑鍏稿瀷鐥涚偣銆?
- ORM 鎻愪緵 **妯″瀷銆佸叧绯汇€佽縼绉伙紙涓?Alembic 鍗忓悓锛?* 鐨勫彲缁存姢鎬э紝姣旀墜鍐欒８ SQL 鏇撮€傚悎鎸佺画杩唬鐨勪笟鍔¤〃缁撴瀯銆?

**鑳借В鍐充粈涔堥棶棰?*

- **骞跺彂涓庡欢杩?*锛氬湪楂樺苟鍙戣澶氬啓鍦烘櫙涓嬫洿濂藉湴鍒╃敤鍗曡繘绋?**I/O 骞惰**銆?
- **鍙淮鎶ゆ€?*锛氳〃缁撴瀯浠?Model 涓庤縼绉绘枃浠朵负 **鍗曚竴浜嬪疄鏉ユ簮**锛屽噺灏戙€岀幆澧冧箣闂?schema 涓嶄竴鑷淬€嶃€?
- **绫诲瀷涓庢牎楠?*锛氫笌 Pydantic 妯″瀷鍒嗗眰閰嶅悎锛?*鍏ュ簱鍓嶆牎楠?* 鏇存竻鏅般€?

### 5锛堿lembic 鏁版嵁搴撹縼绉?

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **Alembic**锛歋QLAlchemy 瀹樻柟鎺ㄨ崘鐨?**鏁版嵁搴?schema 鐗堟湰绠＄悊宸ュ叿**锛岄€氳繃銆岃縼绉昏剼鏈€嶆弿杩?**澧為噺 DDL**锛堝缓琛ㄣ€佸姞鍒椼€佺储寮曘€佸洖婊氾級銆?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- 浼佷笟椤圭洰浠庣涓€澶╁氨瑕佸亣璁?**澶氱幆澧?*锛堝紑鍙戙€佹祴璇曘€侀鍙戙€佺敓浜э級涓?**澶氫汉鍗忎綔**锛涙病鏈夎縼绉诲伐鍏峰垯鍙兘闈犳墜宸ユ墽琛?SQL锛?*涓嶅彲閲嶅銆佷笉鍙璁?*銆?
- 涓?SQLAlchemy Model **鍚屾簮婕旇繘**锛氬厛鏀规ā鍨嬪啀鐢熸垚 / 缂栧啓 revision锛岄檷浣庛€屼唬鐮佷笌搴撶粨鏋勬紓绉汇€嶃€?

**鑳借В鍐充粈涔堥棶棰?*

- **鍙噸澶嶉儴缃?*锛氭柊鐜 `alembic upgrade head` 鍗冲彲瀵归綈 schema銆?
- **鍙洖婊?*锛氬嚭闂鍙?`downgrade` 鏈夎鍒掓挙閫€锛堜粛闇€璋ㄦ厧涓庡浠斤級銆?
- **鍙樻洿瀹¤**锛氭瘡娆¤縼绉绘湁鐗堟湰鍙蜂笌鎻愪氦璁板綍锛屾弧瓒?**鍙樻洿绠＄悊** 涓庢帓鏌ラ渶瑕併€?

### 6锛塒ydantic Settings 闆嗕腑閰嶇疆

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **Pydantic v2 Settings**锛氫粠 **鐜鍙橀噺銆乣.env` 鏂囦欢** 绛夋潵婧愯鍙栭厤缃紝骞跺仛 **绫诲瀷杞崲涓庢牎楠?*锛堝 `DATABASE_URL` 蹇呴』鏄悎娉?URL銆佺鍙ｄ负 int锛夈€?
- **闆嗕腑閰嶇疆**锛氭暟鎹簱 URL銆丣WT 瀵嗛挜銆丩iteLLM 鐩稿叧鐜鍙橀噺绛夊湪 **鍗曚竴 `Settings` 瀵硅薄** 娉ㄥ叆锛岄伩鍏嶅湪浠ｇ爜鍚勫 `os.getenv` 鏁ｈ惤銆?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- 涓?FastAPI **渚濊禆娉ㄥ叆**澶╃劧濂戝悎锛歚get_settings()` 鍙綔涓轰緷璧栵紝渚夸簬鍗曟祴鏃舵浛鎹㈤厤缃€?
- **澶辫触蹇?*锛氬惎鍔ㄦ椂鍗冲彂鐜扮己 key銆佺被鍨嬮敊璇紝鑰屼笉鏄繍琛屽埌涓€鍗婃墠鎶涢敊銆?

**鑳借В鍐充粈涔堥棶棰?*

- **鐜涓€鑷存€?*锛氬噺灏戙€屾垜鏈湴鑳借窇銆佷笂 Docker 灏辨寕銆嶇殑閰嶇疆绫绘晠闅溿€?
- **瀵嗛挜绠＄悊**锛氭槑纭摢浜涘彉閲忓繀濉紝渚夸簬瀵规帴 **K8s Secret / 瀹㈡埛瀵嗛挜鏌?*銆?
- **鏂囨。鍖?*锛氬瓧娈靛嵆鏂囨。锛屾柊鎴愬憳涓婃墜蹇€?

### 7锛夎璇佷笌浼氳瘽锛氭敞鍐?/ 鐧诲綍銆丣WT锛坧ython-jose锛夈€乥crypt锛涘璇?CRUD

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **娉ㄥ唽 / 鐧诲綍**锛氱敤鎴疯韩浠藉叆椹讳笌鍑瘉鏍￠獙锛涘瘑鐮佺粡 **bcrypt** 绛夌畻娉?**鍗曞悜鍝堝笇** 瀛樺偍锛屼笉瀛樻槑鏂囥€?
- **JWT锛圝SON Web Token锛?*锛氭湇鍔＄绛惧彂 **鑷寘鍚０鏄?* 鐨勪护鐗岋紝瀹㈡埛绔湪鍚庣画璇锋眰涓惡甯?**Authorization: Bearer**锛岀敤浜?**鏃犵姸鎬?* 璁よ瘉锛堝彲閰嶅悎 refresh锛夈€?*python-jose** 鐢ㄤ簬缂栫爜 / 瑙ｇ爜涓庢牎楠岀鍚嶃€?
- **瀵硅瘽 CRUD**锛氬銆屼細璇?thread銆嶄笌銆屾秷鎭?messages銆嶇殑鍒涘缓銆佸垪琛ㄣ€佸垹闄ょ瓑锛屾敮鎾戝浼氳瘽浜у搧涓庡悗缁璁°€?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- **绉佹湁鍖?SaaS / 鍐呯綉闂ㄦ埛** 甯歌妯″紡鏄?JWT + REST锛屽墠鍚庣鍒嗙娓呮櫚锛涙棤鐘舵€?API 渚夸簬 **姘村钩鎵╁睍**锛堜細璇濇€佷笉缁戞鍗曟満鍐呭瓨锛夈€?
- bcrypt 涓轰笟鐣岄粯璁ょ殑瀵嗙爜鍝堝笇閫夋嫨涔嬩竴锛屾姉褰╄櫣琛ㄤ笌鏆村姏鐮磋В鎴愭湰鍙鏈熴€?

**鑳借В鍐充粈涔堥棶棰?*

- **澶氱敤鎴烽殧绂?*锛氭病鏈夎璇佸垯鏃犳硶鍋?**鎸夌敤鎴风殑鏁版嵁闅旂** 涓庨厤棰濄€?
- **瀵规帴浼佷笟 SSO 鐨勬紨杩涚┖闂?*锛氬綋鍓?JWT 鍩虹嚎鍙€愭鎵╁睍涓?**OIDC / LDAP** 绛夛紙瑙嗗鎴烽渶姹傦級銆?
- **瀹夊叏鍩虹嚎**锛氶伩鍏嶅急瀵嗙爜瀛樺偍涓庢槑鏂囦細璇?token 婊″ぉ椋炪€?

### 8锛塋LM锛歀iteLLM 缁熶竴缃戝叧涓?SSE 娴佸紡杩斿洖

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **LiteLLM**锛氶潰鍚戝绉嶅ぇ妯″瀷鍘傚晢鐨?**缁熶竴璋冪敤灞?*锛屽皢涓嶅悓 SDK / 绔偣宸紓鏀舵暃涓?**鍏煎 OpenAI 鐨勬帴鍙ｅ舰鎬?*锛屽苟鏀寔 **娴佸紡 chunk**銆佽矾鐢便€佸瘑閽ョ鐞嗙瓑鑳藉姏锛堝叿浣撲互瀹樻柟鐗堟湰涓哄噯锛夈€?
- **SSE锛圫erver-Sent Events锛?*锛氬熀浜?HTTP 鐨?**鍗曞悜娴佸紡** 鎺ㄩ€侊紝娴忚鍣ㄧ敤 `EventSource` 鎴?fetch 娴佽锛涢€傚悎 **閫?token / 閫愭** 鎶婃ā鍨嬭緭鍑烘帹缁欏墠绔€?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- **100+ Provider** 瀵规帴鑻ヨ嚜鐮旈€傞厤灞傛垚鏈珮銆佹槗纰庯紱LiteLLM 鎶娿€屾崲妯″瀷 = 鏀归厤缃€嶄骇鍝佸寲锛岀鍚堝钩鍙板瀷浜у搧 **闄嶄綆杈归檯瀵规帴鎴愭湰** 鐨勭洰鏍囥€?
- 瀵硅瘽绫讳骇鍝?**鐢ㄦ埛浣撴劅** 寮轰緷璧栨祦寮忥紱SSE 鍦ㄦ祻瑙堝櫒涓庝唬鐞嗕笂姣旂函 WebSocket 鏇存槗 **绌块€忛儴鍒嗕紒涓氱綉鍏?*锛堜粛瑙嗗鎴风綉缁滅瓥鐣ヨ€屽畾锛夈€?

**鑳借В鍐充粈涔堥棶棰?*

- **鍘傚晢閿佸畾缂撹В**锛氬悓涓€濂楀悗绔帴鍙ｅ彲鍒囨崲 **鍥藉唴 / 鍥藉 / 绉佹湁鍖?* 妯″瀷渚涘簲鍟嗐€?
- **棣栧瓧寤惰繜锛圱TFB锛?*锛氭祦寮忚緭鍑鸿鐢ㄦ埛鏇村揩鐪嬪埌鍙嶉锛屽噺灏戙€屽崱姝绘劅銆嶃€?
- **缁熶竴瑙傛祴闈?*锛氫究浜庡湪缃戝叧灞傚仛 **鏃ュ織銆侀檺娴併€佽璐瑰煁鐐?*锛堜笌 Phase 5 璺嚎琛旀帴锛夈€?

### 9锛夊墠绔細React + Vite + TailwindCSS + Zustand锛涗笌鍚庣 REST + SSE

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **React**锛氱粍浠跺寲 UI 搴擄紙鐗堟湰浠?`ui/package.json` 涓哄噯锛夈€?
- **Vite**锛氱幇浠ｅ墠绔?**鏋勫缓涓庡紑鍙戞湇鍔″櫒**锛屽喎鍚姩蹇€丠MR 浣撻獙濂姐€?
- **TailwindCSS**锛?*宸ュ叿绫讳紭鍏?* 鐨?CSS 妗嗘灦锛屽揩閫熸惌绠＄悊鍙颁笌瀵硅瘽 UI锛屽噺灏戞墜鍐?CSS 纰庣墖鏂囦欢銆?
- **Zustand**锛氳交閲?**瀹㈡埛绔姸鎬佺鐞?*锛岄€傚悎瀛?**褰撳墠鐢ㄦ埛銆佷細璇濆垪琛ㄣ€佹祦寮忔秷鎭紦鍐插尯** 绛夛紝姣?Redux 鏇磋杽銆?
- **REST + SSE**锛氳璇佷笌 CRUD 璧?**JSON REST**锛涘彂閫佹秷鎭蛋 **SSE** 璇绘祦锛屽墠鍚庣鑱岃矗杈圭晫娓呮銆?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- 浼佷笟鍐呯綉绠＄悊鍙扮被鐣岄潰 **缁勪欢鍖?+ 瀹炵敤鏍峰紡** 鏄富娴佽矾寰勶紱Vite 鎻愬崌 **鍗曚汉鍏ㄦ爤** 寮€鍙戞晥鐜囥€?
- Zustand 瓒冲鏀拺 **浼氳瘽鍒囨崲銆佹祦寮忚拷鍔?* 鑰屼笉寮曞叆杩囬噸鏍锋澘浠ｇ爜銆?

**鑳借В鍐充粈涔堥棶棰?*

- **寮€鍙戞晥鐜?*锛氬揩閫熻凯浠ｅ璇濋〉銆佹ā鍨嬮€夋嫨銆侀敊璇彁绀虹瓑 UX銆?
- **涓庡悗绔绾︽竻鏅?*锛歊EST 鏂囨。涓庣被鍨嬶紙鍙厤鍚?OpenAPI 鐢熸垚 TS 绫诲瀷锛夊噺灏戣仈璋冩懇鎿︺€?
- **娴佸紡 UX**锛歋SE 娑堣垂渚у彲鐙珛澶勭悊 **閲嶈繛銆佷腑鏂€乴oading 鎬?*銆?

### 10锛変氦浠橈細Docker Compose 鎷夎捣搴旂敤涓庢暟鎹簱

**鏄粈涔堛€佸姛鑳戒笌鐢ㄩ€?*

- **Docker**锛氬簲鐢ㄤ笌鍏朵緷璧栦互 **闀滃儚** 浜や粯锛岀幆澧冨樊寮傦紙搴撶増鏈€佺郴缁熷簱锛夎瀹瑰櫒杈圭晫鍚告敹銆?
- **Docker Compose**锛氱敤 **澹版槑寮?YAML** 瀹氫箟澶氬鍣ㄦ嫇鎵戯紙濡?`app` + `postgres`锛夈€佺綉缁溿€佸嵎銆佺幆澧冨彉閲忥紝涓€鏉″懡浠?`docker compose up` 鎷夎捣鏁村銆?

**涓轰綍閫夌敤锛堣€冮噺锛?*

- 绉佹湁鍖栧鎴风幇鍦哄線寰€鏄?**銆岀粰涓€鍙?Linux + 鍐呯綉浠撳簱銆?*锛汣ompose 鏄渶浣庢懇鎿︾殑 **鍙噸澶嶆紨绀轰笌 PoC** 浜や粯褰㈡€併€?
- PostgreSQL 涓庝笟鍔＄増鏈彲 **閽夋鍦?compose 鏂囦欢**锛屽噺灏戙€屽彛澶翠氦鎺ャ€嶅鑷寸殑鐗堟湰婕傜Щ銆?

**鑳借В鍐充粈涔堥棶棰?*

- **涓€閿鐜?*锛氶攢鍞?/ 鍞墠 / 瀹㈡埛杩愮淮鐢ㄥ悓涓€濂楁枃浠惰捣鐜锛岀缉鐭?**浠?0 鍒板彲鐐归€?* 鐨勬椂闂淬€?
- **闅旂涓庡洖婊?*锛氬鍣ㄥ垹浜嗛噸寤猴紝閰嶅悎 volume 绛栫暐鎺у埗 **鏁版嵁鏄惁鎸佷箙鍖?*銆?
- **涓?K8s 婕旇繘閾鸿矾**锛欳ompose 楠岃瘉绋冲畾鍚庯紝鍙皢闀滃儚涓庨厤缃?**杩佺Щ鍒?Helm / K8s**锛岃€岄潪浠庨浂鍙戞槑閮ㄧ讲鏁呬簨銆?

---

## 瑙勫垝鑳藉姏鎬昏锛圥hase 2鈥?锛?

涓庣畝鍘?/ 璺嚎鍥捐〃杩颁竴鑷达紙**瀹炵幇杩涘害瑙佹枃棣栬〃鏍?*锛夛細

- **Phase 2**锛欰gent CRUD銆?*ReAct** 鎵ц鍣ㄣ€佸伐鍏锋敞鍐岃〃銆?*MCP 瀹㈡埛绔?*銆佹墽琛屽巻鍙层€?
- **Phase 3**锛氬伐浣滄祦寮曟搸锛圝SON DAG銆佹嫇鎵戞帓搴忋€佸紓姝ュ苟琛屻€佸彉閲忔ā鏉匡級銆?
- **Phase 4**锛氱煡璇嗗簱 / RAG锛堜笂浼犮€佸垎鍧椼€佸祵鍏ャ€乸gvector 妫€绱€佷笌 Agent / 宸ヤ綔娴侀泦鎴愶級銆?
- **Phase 5**锛氬绉熸埛銆佺敤閲忎笌璁¤垂銆丳rometheus銆佺粨鏋勫寲鏃ュ織銆?*correlation ID** 鍏ㄩ摼璺瓑銆?
- **Phase 6**锛氬伐浣滄祦鍙鍖栵紙濡?React Flow锛夈€佺煡璇嗗簱绠＄悊銆佺敓浜х骇 Compose锛圢ginx 绛夛級銆?

---

## 鎶€鏈爤鎬昏

| 鍒嗗眰 | 鎶€鏈€夊瀷 |
|------|----------|
| **杩愯鏃?* | Python 3.12 |
| **Web 妗嗘灦** | FastAPI |
| **ORM / DB 椹卞姩** | SQLAlchemy 2.0 async + **asyncpg** |
| **鏁版嵁搴?* | PostgreSQL 16 + **pgvector** |
| **閰嶇疆** | Pydantic Settings |
| **杩佺Щ** | Alembic |
| **LLM 缃戝叧** | LiteLLM锛堝鍘傚晢缁熶竴鍏ュ彛銆佹祦寮忥級 |
| **璁よ瘉** | JWT锛坧ython-jose锛? bcrypt |
| **鍓嶇** | React + Vite + TailwindCSS + Zustand |
| **瀹瑰櫒** | Docker Compose |

---

## 鏋舵瀯璁捐

鏈妭鎶?**璇锋眰璺緞鎬昏**銆?*鍒嗗眰涓庣粍浠?*銆?*浠撳簱鐩綍** 鍚堝苟鍦ㄤ竴澶勶細鍏堢湅鏁版嵁鎬庝箞娴侊紝鍐嶅鐓т唬鐮佽惤鍦ㄥ摢涓寘銆?

### 閫昏緫鏋舵瀯绠€鍥?

```
  ui/ 鈥?REST + SSE
         鈹?
         鈻?
  FastAPI 鈥?core/auth 路 core/chat 路 core/llm 鈫?LiteLLM
         鈹?
         鈻?
  PostgreSQL锛坧gvector 闀滃儚宸插氨缁紱涓氬姟 RAG 瑙?Phase 4锛?
```

### 閫昏緫鍒嗗眰璇﹁В锛堜笌浠撳簱 `src/openagentic/` 鐩綍瑙勫垝涓€鑷达級

```
                    鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                    鈹? React锛堟祻瑙堝櫒 / 鍐呯綉閮ㄧ讲锛?     鈹?
                    鈹? REST锛氳璇併€佸璇?CRUD           鈹?
                    鈹? SSE锛氭祦寮忚ˉ鍏?                  鈹?
                    鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                                    鈹?HTTPS锛堝唴缃戯級
                                    鈻?
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹? FastAPI锛坥penagentic.main锛?                                      鈹?
鈹? 鈹溾攢鈹€ deps锛欴B Session銆佸綋鍓嶇敤鎴凤紙JWT锛?                            鈹?
鈹? 鈹溾攢鈹€ core/auth锛氭敞鍐屻€佺櫥褰曘€乺efresh銆乵e                            鈹?
鈹? 鈹溾攢鈹€ core/chat锛氫細璇濄€佹秷鎭寔涔呭寲                                  鈹?
鈹? 鈹斺攢鈹€ core/llm锛歀iteLLM 灏佽 鈫?鍚勫巶鍟?API                          鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                                鈹?
                                鈻?
鈹屸攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹? PostgreSQL 16                                                     鈹?
鈹? 鈹溾攢鈹€ 涓氬姟琛細鐢ㄦ埛銆佷細璇濄€佹秷鎭瓑                                    鈹?
鈹? 鈹斺攢鈹€ pgvector锛氫负鍚庣画 RAG / 璁板繂妫€绱㈤鐣欙紙璺嚎鍥句腑 Phase 4锛?      鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
```

### 椤圭洰缁撴瀯锛堜唬鐮佸竷灞€锛?

```
src/
鈹溾攢鈹€ openagentic_entry/   # 鎺у埗鍙板叆鍙ｏ細寮曞 pip install -e 鍚庡啀鍔犺浇 CLI锛堣 pyproject [project.scripts]锛?
鈹斺攢鈹€ openagentic/
    鈹溾攢鈹€ main.py              # 搴旂敤宸ュ巶銆乴ifespan銆乻tructlog
    鈹溾攢鈹€ config.py / deps.py
    鈹溾攢鈹€ cli/                 # 缁堢 ReAct CLI锛坋ntry銆乺epl銆乸roviders銆乼ools銆乸latform_adapter 绛夊瓙妯″潡锛?
    鈹溾攢鈹€ core/
    鈹?  鈹溾攢鈹€ auth/            # Phase 1锛氭敞鍐岀櫥褰?JWT
    鈹?  鈹溾攢鈹€ chat/            # Phase 1锛氫細璇濇秷鎭?+ SSE
    鈹?  鈹斺攢鈹€ llm/             # Phase 1锛歀iteLLM
    鈹溾攢鈹€ agent/               # Phase 2 宸插疄鐜帮紙鍩虹鐗堬級
    鈹溾攢鈹€ mcp/                 # Phase 2 宸插疄鐜帮紙鍩虹鐗堬級
    鈹溾攢鈹€ workflow/            # Phase 3 宸插疄鐜?
    鈹溾攢鈹€ knowledge/           # Phase 4 鍗犱綅
    鈹溾攢鈹€ tenant/              # Phase 5 鍗犱綅
    鈹溾攢鈹€ observability/       # Phase 5 鍗犱綅
    鈹斺攢鈹€ db/                  # session銆丅ase
ui/                          # Phase 1 鍓嶇锛汸hase 6 閮ㄥ垎鑳藉姏鎸佺画杩唬
extensions/android/          # 鍙€夋墿灞曪紙鑻ユ湁锛?
alembic/                     # 杩佺Щ鑴氭湰鐩綍锛坮evision 闇€缁存姢锛?
```

**璁捐瑕佺偣**

- **寮傛浼樺厛**锛氭暟鎹簱涓庝細璇濋摼璺噰鐢?async锛岄伩鍏嶉樆濉炰簨浠跺惊鐜紝鍒╀簬楂樺苟鍙戜笅鐨?SSE 闀胯繛鎺ュ満鏅墿灞曘€?
- **缃戝叧鎶借薄**锛歀iteLLM 灏嗐€屾ā鍨嬪悕銆乥ase_url銆佸瘑閽ャ€佹祦寮忓崗璁€嶅樊寮傛敹鍙ｅ埌缁熶竴閰嶇疆锛屼骇鍝佷晶鍙毚闇层€屽彲閫夋ā鍨嬪垪琛?+ 娴佸紡瀵硅瘽 API銆嶏紝闄嶄綆瀵规帴鏂板巶鍟嗙殑杈归檯鎴愭湰銆?
- **鍗曚綋婕旇繘璺緞**锛氬綋鍓嶄负 **妯″潡鍖栧崟浣?*锛坄agent/`銆乣workflow/`銆乣knowledge/`銆乣mcp/` 绛夊寘宸插崰浣嶏級锛屼究浜庡厛璺戦€氭牳蹇冮棴鐜紝鍐嶆寜 Phase 濉厖锛岄伩鍏嶈繃鏃╁井鏈嶅姟鍖栧甫鏉ョ殑杩愮淮璐熸媴銆?
- **CLI 骞冲彴閫傞厤灞?*锛歚openagentic.cli.platform_adapter` 缁熶竴灏佽 Windows / Unix 鍦ㄤ簨浠跺惊鐜瓥鐣ャ€佹寜閿鍙栥€佹竻灞忋€佹枃浠舵潈闄愮瓑宸紓锛屼笟鍔′氦浜掑眰涓嶅啀鏁ｈ惤 `os.name` 鍒嗘敮銆?

---

## 鏍稿績妯″潡涓?API 杈圭晫

| 妯″潡 | 鑱岃矗 | 璇存槑 |
|------|------|------|
| **config** | 鐜鍖哄垎銆佸瘑閽ャ€佹暟鎹簱 URL | Pydantic Settings锛?2-factor 鍙嬪ソ |
| **db** | Session銆丅ase Model | 涓?Alembic 鍗忓悓婕旇繘 schema |
| **auth** | 娉ㄥ唽鐧诲綍銆丣WT銆佸瘑鐮佸搱甯?| 浼佷笟鍐呯綉浠嶉渶鏈€灏忔潈闄愪笌瀹¤瀛楁鎵╁睍浣?|
| **chat** | 澶氫細璇濄€佹秷鎭垪琛ㄣ€佸彂閫佹秷鎭?| SSE 灏?token 娴佸啓鍥炲墠绔紝闇€澶勭悊鏂紑涓庤秴鏃?|
| **llm** | 璋冪敤 LiteLLM | 缁熶竴閿欒绫诲瀷銆侀噸璇曠瓥鐣ャ€乽sage 璁板綍锛堜负鍚庣画璁¤垂鍩嬬偣锛?|

**API 杈圭晫锛堜笌瀹炵幇涓€鑷达級**

- 璁よ瘉锛歚POST /api/auth/register`銆乣/login`銆乣/refresh`锛宍GET /api/auth/me`
- 瀵硅瘽锛歚GET/POST /api/conversations`锛宍GET/POST /api/conversations/{id}/messages`锛堝彂閫佸湪 **`stream=true`** 鏃朵负 **SSE**锛?
- 杩愮淮锛歚GET /health`锛涙ā鍨嬶細`GET /api/models`
- **`/api/agents`**銆乣/api/agents/{id}/execute`銆乣/api/agents/{id}/executions`銆乣/api/agent/message` 宸插湪 Phase 2 鎻愪緵鏈€灏忓彲鐢ㄥ疄鐜帮紱`/api/sessions`銆乣/api/channels` 涓?`/api/presence` 浠嶄繚鐣欏吋瀹规€?stub銆?

---

## 宸ョ▼鍖栦笌闈炲姛鑳介渶姹?

- **鍙儴缃叉€?*锛欴ocker Compose 瀹氫箟 Postgres 涓庡簲鐢ㄤ緷璧栵紝渚夸簬鍦ㄥ鎴峰唴缃戝鐜扮浉鍚屾嫇鎵戯紱Postgres 鏈嶅姟寤鸿閰嶇疆 **healthcheck**锛屽簲鐢?**`depends_on` 鏉′欢** 绛夊緟鏁版嵁搴撳氨缁€?
- **鍙娴嬫€э紙璺嚎锛?*锛歅hase 5 鏄庣‘ Prometheus銆乻tructlog銆乧orrelation ID 鈥斺€?涓?**Agent 鍙娴嬫€?* 瀛︿範涓婚瀵归綈锛堣法璇锋眰 trace锛夈€?*褰撳墠浠撳簱**锛歚structlog` 宸插湪鍚姩璺緞鎺ュ叆锛涘叾浣欐寜璺嚎鍥捐凯浠ｃ€?
- **瀹夊叏**锛欽WT + bcrypt 鍩虹嚎锛涘悗缁绉熸埛涓?**鎿嶄綔瀹¤** 闇€涓庝細璇濄€佹ā鍨嬭皟鐢ㄦ棩蹇楀叧鑱斻€?
- **闈欐€佷唬鐮佽川閲?*锛氬凡鎺ュ叆 SonarCloud锛堣 `.github/workflows/sonarcloud.yml` 涓?`sonar-project.properties`锛夛紝PR 浼氬熀浜庢祴璇曡鐩栫巼鍋氳川閲忓垎鏋愩€?
- **璐ㄩ噺涓庡畨鍏ㄦ鏌ユ祦姘寸嚎**锛氭柊澧?`.github/workflows/quality-security.yml`锛岃鐩?`ruff`銆乣mypy`銆乣bandit`銆乣pip-audit` 涓?`schemathesis`锛堝姩鎬?API 妫€鏌ワ級銆?

### SonarCloud 閰嶇疆璇存槑

1. 鍦?SonarCloud 鍒涘缓椤圭洰骞剁粦瀹氭湰浠撳簱銆?
2. 鍦?GitHub 浠撳簱 `Settings -> Secrets and variables -> Actions` 涓坊鍔狅細
   - `SONAR_TOKEN`锛堝繀闇€锛?
3. 棣栨鎵ц鍙湪 Actions 椤垫墜鍔ㄨЕ鍙?`SonarCloud` 宸ヤ綔娴併€?
4. 璐ㄩ噺瑙勫垯銆佽川閲忛棬绂侊紙Quality Gate锛夊湪 SonarCloud 椤圭洰鍚庡彴閰嶇疆銆?

### 鏈湴鎵ц璐ㄩ噺妫€鏌?

```bash
# 闈欐€佽川閲?
ruff check src tests
mypy
bandit -r src/openagentic -c pyproject.toml

# 渚濊禆婕忔礊
pip-audit

# 鍔ㄦ€?API 妫€鏌ワ紙鍏叡鏃犻壌鏉冪鐐癸級
APP_ENV=production PYTHONPATH=src uvicorn openagentic.main:app --host 127.0.0.1 --port 8000
curl -fsS http://127.0.0.1:8000/openapi.json -o openapi.json
python -c "import json; s=json.load(open('openapi.json')); keep={'/health','/api/models','/api/sessions','/api/channels','/api/presence'}; s['paths']={k:v for k,v in s.get('paths',{}).items() if k in keep}; json.dump(s, open('openapi.public.json','w'), ensure_ascii=False, indent=2)"
schemathesis run --url http://127.0.0.1:8000 --include-method GET --max-examples 20 ./openapi.public.json
```

---

## 闅剧偣涓庡彇鑸?

- **銆屼紒涓氱骇銆嶄笌杩唬閫熷害**锛氬厛瀹屾垚 **璐﹀彿 + 澶氫細璇?+ 娴佸紡 + 鑷缓搴?*锛屽啀鍙?Agent / MCP / RAG锛岄伩鍏嶄竴娆℃€уぇ鑰屽叏瀵艰嚧鏃犳硶浜や粯鍙紨绀虹増鏈€?
- **pgvector 涓庡叧绯诲簱鍚屽疄渚?*锛氱畝鍖栬繍缁翠笌浜嬪姟杈圭晫锛涜秴澶ц妯℃椂鍐嶈瘎浼板悜閲忓簱鎷嗗垎銆?
- **鍓嶇涓庡悗绔В鑰?*锛歊EST / SSE 濂戠害娓呮櫚锛屼究浜庢湭鏉ユ浛鎹㈢鐞嗙鎶€鏈爤鎴栧鍔犵Щ鍔ㄧ銆?

---

## 涓€娆℃祦寮忓璇濊姹傜殑瀹屾暣鐢熷懡鍛ㄦ湡

> 浠庣敤鎴风偣鍑诲彂閫佸埌鐪嬪埌鍥炲锛屽悗绔畬鏁撮摼璺涓嬶細

```
鐢ㄦ埛鐐瑰嚮銆屽彂閫併€?
  鈫?鍓嶇 POST /api/conversations/{id}/messages  (body: { content: "浣犲ソ", stream: true } 绛夛紝浠?OpenAPI 涓哄噯)
  鈫?Nginx / 鍙嶅悜浠ｇ悊杞彂锛堝鏈夛級
  鈫?FastAPI 璺敱鍖归厤
  鈫?渚濊禆娉ㄥ叆锛歡et_current_user() 浠?Authorization header 鍙?JWT 鈫?python-jose 楠岀 鈫?鍙?sub(user_id) 鈫?鏌ュ簱纭鐢ㄦ埛瀛樺湪
  鈫?渚濊禆娉ㄥ叆锛歡et_db_session() 浠庤繛鎺ユ睜鍙?AsyncSession
  鈫?Service 灞傦細
    1. 楠岃瘉 conversation_id 灞炰簬 current_user锛堥槻瓒婃潈锛?
    2. 灏嗙敤鎴锋秷鎭啓鍏?messages 琛紙role="user"锛?
    3. 浠?messages 琛ㄦ媺璇ヤ細璇濆巻鍙叉秷鎭紙鎸夋椂闂存帓搴忥紝鍙兘鎴柇鍒版渶杩?N 鏉′互鎺у埗 token锛?
    4. 鏋勯€?messages 鍒楄〃锛歔system_prompt, ...history, user_message]
    5. 璋冪敤 LiteLLM acompletion(model="...", messages=..., stream=True)
  鈫?LiteLLM 鍐呴儴锛?
    - 鏍规嵁 model 鍓嶇紑璺敱鍒板搴?Provider
    - 鎷兼帴 base_url + api_key锛堜粠鐜鍙橀噺 / Settings锛?
    - 鍙戣捣 HTTPS 璇锋眰鍒版ā鍨嬪巶鍟?API
  鈫?妯″瀷鍘傚晢杩斿洖娴侊紙SSE / chunk锛?
  鈫?鍚庣 StreamingResponse锛?
    async for chunk in llm_stream:
      text_delta = chunk.choices[0].delta.content  # 浠ュ疄闄?chunk 缁撴瀯涓哄噯锛岄渶闃插尽鎬цВ鏋?
      yield f"data: {json.dumps({'content': text_delta})}\n\n"
    # 娴佺粨鏉熷悗
    灏嗗畬鏁?assistant 鍥炲鍐欏叆 messages 琛紙role="assistant"锛?
    璁板綍 token usage锛坕nput_tokens, output_tokens锛夊埌鏃ュ織鎴栬〃
    yield f"data: [DONE]\n\n"   # 鎴栭」鐩害瀹氱殑浜嬩欢褰㈡€?
  鈫?鍓嶇 fetch ReadableStream 娑堣垂锛?
    閫?chunk 杩藉姞鍒版秷鎭皵娉★紝瀹炵幇鎵撳瓧鏈烘晥鏋?
    鏀跺埌缁撴潫浜嬩欢鍚庢爣璁版秷鎭畬鎴?
```

**鍏抽敭缁嗚妭**

- **鏂繛澶勭悊**锛氬鏋滅敤鎴峰湪娴佸紡杩囩▼涓叧闂〉闈紝FastAPI 浼氭姏 `asyncio.CancelledError`锛岄渶瑕佸湪 try / finally 涓?**鍙栨秷涓婃父璇锋眰**锛堥伩鍏嶇櫧鑰?token锛夊苟 **灏嗗凡鐢熸垚鐨勯儴鍒嗗唴瀹瑰瓨搴?*銆?
- **閿欒澶勭悊**锛氭ā鍨?API 杩斿洖 429锛堥檺娴侊級鏃讹紝LiteLLM 鍙厤缃?**鑷姩閲嶈瘯 + 鎸囨暟閫€閬?*锛涜繑鍥?500 鏃堕檷绾у埌澶囩敤妯″瀷鎴栬繑鍥炲弸濂介敊璇€?
- **Token 鎴柇**锛氬鏋滃巻鍙叉秷鎭お闀胯秴杩囨ā鍨?context window锛岄渶瑕佸湪鏋勯€?messages 鏃?**浠庢渶鏃╃殑娑堟伅寮€濮嬩涪寮?*锛屼繚鐣?system prompt + 鏈€杩戠殑瀵硅瘽銆?

---

## 寮€鍙戣矾绾?Phase 0鈥?锛圱odo锛?

### Phase 0锛氳剼鎵嬫灦 + Docker锛堝凡瀹屾垚锛?

- [x] FastAPI 搴旂敤宸ュ巶 + 鐢熷懡鍛ㄦ湡锛堝惈 `structlog` 鍚姩鏃ュ織锛?
- [x] PostgreSQL锛坄pgvector/pgvector:pg16`锛? Docker Compose + healthcheck
- [x] SQLAlchemy 2.0 async ORM + Alembic 宸ョ▼
- [x] Pydantic Settings銆佸仴搴锋鏌ャ€丆ompose 鍩虹鎷撴墤

### Phase 1锛氳璇?+ 鑱婂ぉ + LLM 娴佸紡锛堝凡瀹屾垚锛?

- [x] 娉ㄥ唽 / 鐧诲綍 / JWT
- [x] 浼氳瘽涓庢秷鎭?CRUD
- [x] LiteLLM 瀵规帴 + SSE 娴佸紡杩斿洖
- [x] `ui/` 涓?Phase 1 API 鍗忓悓

### Phase 2锛欰gent 绯荤粺 + MCP锛堝熀纭€鐗堝凡瀹屾垚锛?

- [x] Agent CRUD
- [x] 鏈€灏?ReAct 鎵ц鍣?
- [x] 宸ュ叿娉ㄥ唽琛?
- [x] MCP Client锛圚TTP JSON-RPC锛?
- [x] 鎵ц鍘嗗彶钀藉簱涓庢煡璇?

### Phase 3锛氬伐浣滄祦寮曟搸锛堝凡瀹屾垚锛?

- [x] Workflow CRUD銆佽繍琛岃Е鍙戙€佽繍琛屾煡璇€佽繍琛屽彇娑?
- [x] JSON DAG 鏍￠獙 + 鎷撴墤鎵ц
- [x] 妯℃澘鍙橀噺浼犲弬锛坄{{input.*}}` / `{{nodes.*}}`锛?
- [x] 鑺傜偣绾ч噸璇?/ 瓒呮椂 + 缁撴瀯鍖?trace
- [x] 瀵瑰簲娴嬭瘯瑕嗙洊锛圓PI銆佽竟鐣岃涓恒€侀厤缃寔涔呭寲锛?

### Phase 4锛氱煡璇嗗簱 / RAG锛堟湭瀹屾垚锛?

- [ ] 鏂囨。涓婁紶涓庣鐞?
- [ ] 鍒嗗潡涓庡祵鍏ョ敓鎴?
- [ ] pgvector 妫€绱?
- [ ] 涓?Agent / Workflow 闆嗘垚

### Phase 5锛氬绉熸埛 + 璁¤垂 + 鍙娴嬫€э紙鏈畬鎴愶級

- [ ] 澶氱鎴蜂笌缁勭粐闅旂
- [ ] 鐢ㄩ噺缁熻 / 璁¤垂 / 閰嶉
- [ ] Prometheus 鎸囨爣涓庡憡璀?
- [ ] correlation ID 鍏ㄩ摼璺拷韪?

### Phase 6锛氬墠绔寮猴紙杩涜涓級

- [x] `ui/` 澶氶〉闈紙Sessions銆丼ettings銆丼kills銆丆hannels銆丏evices锛?
- [ ] 宸ヤ綔娴佸彲瑙嗗寲缂栬緫鍣紙React Flow锛?
- [ ] 鐭ヨ瘑搴撶鐞?UI
- [ ] Agent 妯℃澘甯傚満
- [ ] 鐢熶骇绾?Nginx + Compose 鎷撴墤闂幆

---

## 蹇€熷惎鍔?

```bash
git clone https://github.com/openagentic-ai/open-agentic.git
cd open-agentic

# 寤鸿 Python 3.12 + venv
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 蹇呴』鍦ㄤ粨搴撴牴鐩綍鎵ц涓€娆″彲缂栬緫瀹夎锛屽惁鍒?`openagentic` / `import openagentic` 浼氭姤鎵句笉鍒版ā鍧?
pip install -e ".[dev]"     # 浠?pyproject / README 浠撳簱璇存槑涓哄噯

cp .env.example .env
# 濉啓 DATABASE_URL銆丣WT 瀵嗛挜銆佸悇鍘傚晢 API Key / LiteLLM 鎵€闇€鍙橀噺

docker compose up -d postgres
# 寰?Alembic revision 榻愬叏鍚庯細alembic upgrade head
# 寮€鍙戠幆澧冿紙涓?APP_ENV=development锛夛細鍙兘鐢?create_all 寤鸿〃锛岃涓婃枃

PYTHONPATH=src uvicorn openagentic.main:app --host 0.0.0.0 --port 8000
```

- **Swagger / OpenAPI**锛歚http://<host>:8000/docs`
- **鍋ュ悍妫€鏌?*锛歚http://<host>:8000/health`
- **鍓嶇**锛氳繘鍏?`ui/` 鎸?`package.json` 鑴氭湰鍚姩锛堝 `npm install && npm run dev`锛夛紝API 鍩哄湴鍧€鎸囧悜鍚庣銆?

**Windows 琛ュ厖**

- 鎷変唬鐮佹垨鍒囨崲鍒嗘敮鍚庯紝鑻ユ敼浜嗕緷璧栨垨鍏ュ彛锛岃鍦ㄤ粨搴撴牴鐩綍鍐嶆鎵ц锛歚pip install -e .`锛堟垨 `pip install -e ".[dev]"`锛夈€?
- 鎺у埗鍙板懡浠?`openagentic` 鐢?`openagentic_entry` 鍖呭紩瀵硷細鑻ュ皻鏈畨瑁呭彲缂栬緫鍖咃紝棣栨杩愯浼氬皾璇曡嚜鍔ㄦ墽琛?`pip install -e <浠撳簱鏍?`锛涗粛澶辫触鏃惰鎵嬪姩鎵ц涓婁竴琛岀殑 `pip`銆?
- 鍦?Windows 涓婏紝CLI **涓嶄細**鍦ㄨ繘绋嬪唴鑷姩鍙嶅鎵ц `pip install -e .`锛堥伩鍏嶆浛鎹㈡鍦ㄤ娇鐢ㄧ殑鍚姩鍣ㄨ剼鏈鑷村け璐ユ垨 WinError 32锛夛紱婧愮爜鏈夋洿鏂版椂璇疯嚜琛岄噸瑁呭彲缂栬緫鍖咃紝鎴栫洿鎺ヤ娇鐢?`python -m openagentic.cli`銆?

---

## CLI 妯″紡锛堢洿鎺ュ璇濓級

鏃犻渶鍚姩 Web 鏈嶅姟锛岀洿鎺ュ湪缁堢涓庢ā鍨嬪璇濓紙鏀寔鏈湴 Ollama 鎴?OpenAI 鍏煎缃戝叧锛夛細

```bash
cd /opt/open-agentic && source .venv/bin/activate

# 榛樿浣跨敤 qwen3:14b
python -m openagentic.cli

# 浣跨敤 OpenAI 鍏煎缃戝叧锛堝 DeepSeek锛?
python -m openagentic.cli --provider openai -m deepseek-chat

# 鎸囧畾妯″瀷
python -m openagentic.cli -m ollama/deepseek-r1:32b

# 甯︾郴缁熸彁绀?
python -m openagentic.cli -s "浣犳槸涓€涓狿ython涓撳锛岀敤涓枃鍥炵瓟"

# 涔熷彲浠ョ敤娉ㄥ唽鐨勫懡浠わ紙闇€宸?pip install -e .锛?
openagentic
```

`pyproject.toml` 涓?`openagentic` 鍏ュ彛鎸囧悜 **`openagentic_entry:main`**锛氬厛淇濊瘉鍖呭彲瀵煎叆锛屽啀璋冪敤 `openagentic.cli`銆傝嫢鍑虹幇 `ModuleNotFoundError: No module named 'openagentic'` 鎴?`'openagentic_entry'`锛屼竴寰嬪湪浠撳簱鏍圭洰褰曟墽琛?`pip install -e .` 鍚庨噸璇曘€?

CLI Provider 璇存槑锛?

- `--provider auto`锛堥粯璁わ級锛氭寜妯″瀷鍓嶇紑鎴栭粯璁ら厤缃嚜鍔ㄩ€夋嫨 provider銆?
- `--provider <id>`锛氬彲鎸囧畾 `openai`銆乣anthropic`銆乣xai`銆乣gemini`銆乣deepseek`銆乣qwen`銆乣ollama` 绛夈€?
- CLI 鍐呭彲鐢?`/providers` 鏌ョ湅鍘傚晢鍒楄〃锛宍/provider <id>` 鍒囨崲骞惰繘鍏ヨ鍘傚晢閰嶇疆鍚戝锛宍/provider-config [id]` 鍗曠嫭缂栬緫閰嶇疆銆?
- 鏈厤缃繀闇€鐨?API Key 鏃讹紝CLI 浼氬湪杩涘叆浼氳瘽鍓嶅己鍒惰繘鍏ラ厤缃悜瀵硷紝閰嶇疆瀹屾垚鍚庢墠鍏佽缁х画浣跨敤銆?
- 妯″瀷濮嬬粓鐢辨樉寮忛厤缃喅瀹氾紙`-m`銆乣/model`銆乣default_model`銆乣OPENAI_CHAT_MODEL`锛夛紱API Key 浠呯敤浜庨壌鏉冿紝涓嶈礋璐ｂ€滄寚瀹氭ā鍨嬧€濄€?
- Provider 閰嶇疆鏂囦欢榛樿浣嶄簬 `.openagentic/model_providers.json`锛堝彲閫氳繃 `MODEL_PROVIDER_CONFIG_PATH` 璋冩暣锛夈€?

CLI 鍐呯疆鍛戒护锛?

| 鍛戒护 | 璇存槑 |
|------|------|
| `/clear` | 娓呴櫎瀵硅瘽鍘嗗彶 |
| `/model ollama/qwen3:4b` | 鍒囨崲妯″瀷 |
| `/system <prompt>` | 璁剧疆绯荤粺鎻愮ず |
| `/quit` | 閫€鍑?|

DeepSeek锛圤penAI 鍏煎锛夌ず渚嬶細

| 鍦烘櫙 | 寤鸿妯″瀷 |
|------|------|
| 榛樿瀵硅瘽锛圴3.2 闈炴€濊€冿級 | `deepseek/deepseek-chat` |
| 鎺ㄧ悊浼樺厛锛圴3.2 鎬濊€冩ā寮忥級 | `deepseek/deepseek-reasoner` |

璇存槑锛氬綋鍓嶅唴缃?DeepSeek profile 鐨勬ā鍨嬮『搴忎负 `deepseek-reasoner` 浼樺厛浜?`deepseek-chat`銆?

鍙敤妯″瀷锛圤llama 鏈湴锛夛細

| 妯″瀷 | 璇存槑 |
|------|------|
| `ollama/qwen3:14b` | Qwen3 14B锛堥粯璁わ紝甯︽€濊€冿級 |
| `ollama/qwen3:14b-nothink` | Qwen3 14B锛堟棤鎬濊€冿紝鏇村揩锛?|
| `ollama/qwen3:4b` | Qwen3 4B锛堣交閲忥紝甯︽€濊€冿級 |
| `ollama/qwen3:4b-nothink` | Qwen3 4B锛堣交閲忥紝鏃犳€濊€冿級 |
| `ollama/deepseek-r1:32b` | DeepSeek R1 32B |

---

## API 绔偣

### 璁よ瘉

- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/refresh`
- `GET /api/auth/me`

### 瀵硅瘽

- `GET/POST /api/conversations`
- `GET/DELETE /api/conversations/{id}`
- `GET/POST /api/conversations/{id}/messages`锛?*娴佸紡**锛氭煡璇㈠弬鏁版垨 body 涓甫 `stream=true` 绛夛紝浠?`/docs` 涓哄噯锛?

### 鍏朵粬

- `GET /health`
- `GET /api/models`
- `GET /api/llm/providers`銆乣PUT /api/llm/providers/{provider_id}`銆乣PUT /api/llm/default-model`
- `GET/POST /api/agents`銆乣GET/PATCH/DELETE /api/agents/{agent_id}`銆乣POST /api/agents/{agent_id}/execute`
- `GET /api/agents/{agent_id}/executions`銆乣POST /api/agent/message`
- `GET /api/sessions`銆乣GET /api/channels`銆乣GET /api/presence` 浠嶄负绠€鍖栨々鍝嶅簲锛堝吋瀹规棫鍓嶇锛夈€?

---

## 鍓嶇 `ui/`

- 鎶€鏈爤锛?*React + Vite + TailwindCSS + Zustand**锛堢増鏈互浠撳簱涓哄噯锛夈€?
- **涓庡悗绔崗浣?*锛歊EST 瀹屾垚璁よ瘉涓庝細璇?CRUD锛涘彂閫佹秷鎭€氳繃 **SSE** 娑堣垂娴佸紡澧為噺銆?
- **褰撳墠椤甸潰鑳藉姏锛堢ず渚嬶級**锛歋essions銆丼ettings銆丼kills銆丆hannels銆丏evices 绛?鈥斺€?浠?`ui/src` 璺敱涓庨〉闈负鍑嗭紱**宸ヤ綔娴佸彲瑙嗗寲銆佺煡璇嗗簱杩愯惀鍚庡彴** 绛夊睘浜庤矾绾垮浘 Phase 6 / Phase 4 鑱斿姩鑳藉姏锛?*鏈壙璇哄凡鍏ㄩ儴鍙敤**銆?

---

## 甯歌闂涓庢帓閿?

1. **鏁版嵁搴撹繛涓嶄笂**锛氭鏌?`DATABASE_URL` 鏄惁涓?Compose 绔彛銆佸簱鍚嶃€佺敤鎴峰瘑鐮佷竴鑷达紱纭 Postgres 瀹瑰櫒 **healthy** 鍚庡啀鍚姩 app銆?
2. **琛ㄤ笉瀛樺湪**锛氳嫢灏氭棤 Alembic `upgrade`锛屽湪 **寮€鍙戠幆澧?* 纭 `APP_ENV=development` 涓?`create_all` 琛屼负锛?*鐢熶骇绂佹**渚濊禆 `create_all`銆?
3. **SSE 琚唬鐞嗙紦鍐?*锛歂ginx 闇€鍏抽棴鍝嶅簲缂撳啿锛堝 `proxy_buffering off`锛夈€佸悎鐞?`proxy_read_timeout`锛屽惁鍒欐墦瀛楁満鏁堟灉寤惰繜銆?
4. **妯″瀷 401 / 429**锛氭牳瀵圭幆澧冨彉閲忎腑鐨?Key 涓?LiteLLM 璺敱锛涢檺娴佹椂鍔犻噸璇曟垨闄嶇骇妯″瀷銆?
5. **娴佷腑鏂悗 DB 鍙湁鍗婃潯**锛氭鏌ュ彇娑堣矾寰勬槸鍚﹀湪 finally 涓?**钀藉簱 partial** 骞?**鍙栨秷涓婃父**銆?
6. **`openagentic` 鎶?`ModuleNotFoundError: No module named 'openagentic'`锛堟垨 `openagentic_entry`锛?*锛氭湭鍦ㄤ粨搴撴牴鐩綍鎵ц鍙紪杈戝畨瑁呫€傚厛 `cd` 鍒板厠闅嗕笅鏉ョ殑浠撳簱鏍圭洰褰曪紝婵€娲?venv锛屾墽琛?`pip install -e .`锛屽啀杩愯 `openagentic` 鎴?`python -m openagentic.cli`銆?
7. **pip 鍙嶅鎻愮ず `Ignoring invalid distribution ~...`锛堝 `~penagentic`锛?*锛氬涓轰笂娆″畨瑁呬腑鏂暀涓嬬殑鎹熷潖鐩綍銆傚叧闂墍鏈変娇鐢ㄨ venv 鐨勮繘绋嬪悗锛屽湪 `.venv\Lib\site-packages`锛堟垨瀵瑰簲 venv 鐨?`site-packages`锛変腑鍒犻櫎鍚嶇О浠?`~` 寮€澶淬€佷笖鏄庢樉涓?`openagentic` 鐩稿叧鐨勬枃浠跺す锛屽啀鎵ц `pip install -e .`銆?

---

## 浠撳簱涓庤础鐚?

- **GitHub**锛歔openagentic-ai/open-agentic](https://github.com/openagentic-ai/open-agentic)
- 娆㈣繋 Issue / PR锛涘ぇ鍔熻兘寤鸿鍏堝鐓?**Phase 璺嚎鍥?* 寮€璁ㄨ锛岄伩鍏嶄笌鍗犱綅鍖呰璁″啿绐併€?

---

## 璁稿彲璇?

MIT
