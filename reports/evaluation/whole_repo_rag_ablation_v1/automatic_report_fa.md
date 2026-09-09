# گزارش آزمایش Whole Repository در برابر RAG

## وضعیت

بنچمارک held-out شامل ۱۸ مفهوم و ۳۶ سؤال دوزبانه روی سه snapshot فریز‌شده اجرا شد. برای هر سؤال چهار بازو تعریف شد: Whole Repository، Lexical RAG، Semantic RAG با `gemini-embedding-2` و Hybrid RAG با همان embedding. مدل مولد در همه بازوها `glm-5.3-flash`، دما صفر و سقف context بازیابی ۶۰۰۰ نویسه بود.

اجرای اصلی ۱۴۴ رکورد تولید کرد. پس از یک retry مستقل برای failureهای قابل‌بازیابی، ۱۲۰ پاسخ قابل داوری، ۱۲ failure و ۱۲ مورد unavailable باقی ماند. هر ۱۲ مورد unavailable متعلق به Whole Repository در مخزن CodeCompass است.

## نتیجه اصلی بازیابی

Evidence recall روی همه ۳۰ سؤال مثبت و بدون حذف failureهای generation محاسبه شد:

| بازو | Evidence recall |
|---|---:|
| Lexical RAG | 22.22% |
| Semantic RAG | 64.72% |
| Hybrid RAG | 56.67% |

در واحد مفهوم دوزبانه، Semantic نسبت به Lexical به‌طور متوسط ۴۲.۵ واحد درصد بهتر بود؛ bootstrap زوجی با ۱۰٬۰۰۰ نمونه و seed ثابت، CI95 برابر ۲۸.۳۳ تا ۵۶.۹۴ واحد درصد داد. Hybrid نیز نسبت به Lexical ۳۴.۴۴ واحد درصد بهتر بود و CI95 آن ۲۱.۶۷ تا ۴۷.۷۸ بود. چون هر دو بازه اطمینان کاملاً بالاتر از صفر هستند، این بنچمارک شواهد آماری مثبت برای سودمندی embedding در بازیابی ارائه می‌کند.

Semantic در این مجموعه از Hybrid بهتر بود. بنابراین ادعای درست این نیست که «Hybrid همیشه بهترین است»؛ ادعای قابل دفاع این است که هر دو روش embedding-based از lexical-only بهتر بودند و Semantic در این held-out benchmark بالاترین evidence recall را داشت.

## Whole Repository و مقیاس‌پذیری

Hospital-System و CS-Bookstore در بازوی Whole Repository قابل اجرا بودند. در CodeCompass، ورودی کامل شامل ۱۰۰ فایل Python، ۸۳۳٬۱۲۹ بایت منبع و ۱٬۲۳۶ chunk بود. یک probe پذیرفته‌شده برای این ورودی حدود ۱۸۰٬۲۱۲ prompt token مصرف کرد، اما درخواست استاندارد و ثابت آزمایش چهار بار با HTTP 400 رد شد. برای جلوگیری از تکرار بی‌فایده، هشت اجرای Whole Repository باقی‌مانده صریحاً unavailable ثبت شدند.

این نتیجه به‌تنهایی نشان نمی‌دهد که کیفیت پاسخ RAG از Whole Repository بهتر است، اما یک مزیت عملی مهم RAG را نشان می‌دهد: بازوهای Lexical، Semantic و Hybrid روی همان مخزن اجرا شدند، در حالی که ارسال کامل repository از trust boundary عملی gateway عبور نکرد. مقایسه کیفیت Whole Repository و RAG باید فقط روی دو مخزن کوچک‌تر و پس از تکمیل blind review گزارش شود.

## توکن، زمان و هزینه پاسخ‌های موفق

| بازو | موفق | ناموفق | unavailable | Prompt tokens | هزینه گزارش‌شده (دلار) | Median latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Whole Repository | 23 | 1 | 12 | 401,289 | 0.029142 | 26.083s | 40.543s |
| Lexical RAG | 32 | 4 | 0 | 31,441 | 0.006422 | 14.209s | 27.066s |
| Semantic RAG | 33 | 3 | 0 | 27,306 | 0.006867 | 15.999s | 30.884s |
| Hybrid RAG | 32 | 4 | 0 | 35,512 | 0.007086 | 16.762s | 27.811s |

میانگین prompt token در پاسخ‌های موفق Whole Repository حدود ۱۷٬۴۴۷ و در Semantic حدود ۸۲۷ بود؛ یعنی تقریباً ۹۵٪ کاهش ورودی. این نسبت توصیفی است، زیرا Whole Repository برای CodeCompass unavailable شد و تعداد پاسخ‌های موفق دو بازو برابر نیست.

کاهش واقعی اعتبار حساب از ۱۲۸٬۶۵۱.۶۸ به ۱۰۳٬۶۰۷.۸۳ تومان، برابر ۲۵٬۰۴۳.۸۵ تومان بود. این عدد علاوه بر اجرای اصلی، pilotهای تشخیص سقف خروجی، query embedding، probe ظرفیت، recovery و سه تلاش ناموفق stability را نیز شامل می‌شود؛ بنابراین نباید آن را صرفاً هزینه ۱۴۴ رکورد اصلی نامید.

## reliability و محدودیت provider

Alias مدل با وجود ارسال `thinking.type=disabled` در برخی پاسخ‌ها reasoning token تولید کرد. سقف اولیه ۱۲۰۰ توکن گاهی تماماً صرف reasoning شد و متن نهایی خالی ماند؛ این pilot جداگانه حفظ شد و وارد نتیجه اصلی نشد. پروتکل اصلی پیش از اجرای کامل با سقف ۲۴۰۰ و پاسخ حداکثر ۲۵۰ کلمه دوباره فریز شد.

در اواخر اجرا gateway چند درخواست هم‌ساختار را با HTTP 400 رد کرد. از ۱۳ failure واجد retry فقط یک مورد بازیابی شد. اجرای stability نیز پس از سه HTTP 400 متوالی متوقف شد تا اعتبار بیهوده مصرف نشود. بنابراین stability پاسخ‌ها در وضعیت فعلی «اندازه‌گیری‌نشده به‌علت provider instability» است، نه صفر و نه موفق.

## آنچه اکنون قابل ادعاست

1. embedding در این بنچمارک بازیابی evidence مرتبط را به‌صورت معنادار نسبت به lexical-only افزایش داد.
2. RAG ورودی مدل و latency را به‌شدت کاهش داد و روی مخزن بزرگ‌تری اجرا شد که Whole Repository با prompt ثابت آزمایش توسط gateway رد شد.
3. هنوز نمی‌توان ادعا کرد کیفیت نهایی پاسخ Semantic یا Hybrid قطعاً از Whole Repository بهتر است؛ این ادعا به امتیازهای blind review برای correctness، fact recall، claim precision، groundedness، completeness و hallucination نیاز دارد.
4. اجرای stability باید در یک بازه سالم provider از checkpoint ادامه یابد؛ failure فعلی باید به‌عنوان محدودیت reliability سرویس گزارش شود.
