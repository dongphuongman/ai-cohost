"""Seed script for demo data.

Run: uv run python seed.py
Requires: database with migration applied.
"""
import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

engine = create_async_engine(settings.database_url)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed():
    async with async_session() as db:
        # Check if already seeded
        result = await db.execute(text("SELECT count(*) FROM users"))
        if result.scalar() > 0:
            print("Database already seeded, skipping.")
            return

        # 1. Demo user
        await db.execute(text("""
        INSERT INTO users (id, email, email_verified, password_hash, full_name)
        VALUES (1, 'demo@cohost.vn', true,
                crypt('demo1234', gen_salt('bf')),
                'Demo User')
        """))

        # 2. Demo shop
        await db.execute(text("""
        INSERT INTO shops (id, name, slug, industry, team_size, owner_user_id, plan, plan_status,
                           trial_ends_at)
        VALUES (1, 'Beauty Demo Shop', 'beauty-demo', 'Mỹ phẩm', '1',
                1, 'pro', 'active', now() + interval '14 days')
        """))

        # 3. Shop member (owner)
        await db.execute(text("""
        INSERT INTO shop_members (shop_id, user_id, role, joined_at)
        VALUES (1, 1, 'owner', now())
        """))

        # 4. Four preset personas
        personas = [
            ("Thân thiện", "Gần gũi, xưng chị/em, tạo cảm giác như người nhà",
             "thân thiện",
             ["Hay dùng emoji trái tim", "Gọi khách là chị/em"],
             ["Dạ chị ơi, sản phẩm này được lắm ạ!", "Em gửi chị thông tin nhé ❤️", "Chị yên tâm, shop mình bảo hành đầy đủ ạ"]),
            ("Năng động", "Trẻ trung, nhiều năng lượng, tạo hứng khởi mua hàng",
             "năng động",
             ["Hay dùng từ trending", "Nói nhanh, ngắn gọn"],
             ["Woww sản phẩm này hot lắm nha!", "Deal hời quá trời luôn á!", "Nhanh tay kẻo hết nha mọi người!"]),
            ("Chuyên nghiệp", "Lịch sự, xưng quý khách, cung cấp thông tin chi tiết",
             "chuyên nghiệp",
             ["Luôn trích dẫn thông số", "Giải thích kỹ lưỡng"],
             ["Kính chào quý khách, sản phẩm này có thành phần chính là...", "Quý khách có thể yên tâm về chất lượng vì...", "Xin phép được tư vấn thêm cho quý khách ạ"]),
            ("Hài hước", "Vui vẻ, nhiều câu đùa, tạo không khí sôi nổi",
             "hài hước",
             ["Hay pha trò", "Dùng câu vần"],
             ["Kem này xịn đến mức da đẹp phải gọi bằng sếp!", "Mua 1 được 2, không mua hơi phí đời nha!", "Giá này mà bỏ qua thì tiếc lắm luôn á!"]),
        ]
        for i, (name, desc, tone, quirks, phrases) in enumerate(personas):
            await db.execute(text("""
            INSERT INTO personas (shop_id, name, description, tone, quirks, sample_phrases,
                                  is_default, is_preset)
            VALUES (1, :name, :desc, :tone,
                    :quirks, :phrases,
                    :is_default, true)
            """), {"name": name, "desc": desc, "tone": tone, "quirks": quirks, "phrases": phrases, "is_default": i == 0})

        # 5. Five sample cosmetic products
        products = [
            ("Kem chống nắng UV Shield SPF50+", "Kem chống nắng phổ rộng, bảo vệ da khỏi tia UVA/UVB, không gây nhờn, phù hợp mọi loại da. Chiết xuất từ centella asiatica giúp làm dịu da.",
             350000, "Mỹ phẩm",
             ["SPF50+ PA++++", "Không gây nhờn", "Chiết xuất centella", "Phù hợp da nhạy cảm", "Dùng được cho mặt và body"]),
            ("Serum Vitamin C 20% Brightening", "Serum sáng da chứa 20% Vitamin C nguyên chất, kết hợp Niacinamide và Hyaluronic Acid. Làm mờ thâm nám sau 4 tuần sử dụng.",
             480000, "Mỹ phẩm",
             ["20% Vitamin C nguyên chất", "Kết hợp Niacinamide 5%", "Hyaluronic Acid cấp ẩm", "Mờ thâm sau 4 tuần", "Chai thủy tinh tối màu bảo quản tốt"]),
            ("Son môi lì Velvet Matte", "Son môi lì mịn như nhung, lên màu chuẩn, giữ màu đến 8 tiếng. Bảng màu 12 shade phù hợp tone da Việt Nam.",
             220000, "Mỹ phẩm",
             ["Lì mịn như nhung", "Giữ màu 8 tiếng", "12 shade phù hợp da Việt", "Không chì, không paraben", "Dưỡng ẩm nhẹ"]),
            ("Tẩy trang micellar water 500ml", "Nước tẩy trang dịu nhẹ, làm sạch sâu mà không cần rửa lại. Công thức không cồn, phù hợp da nhạy cảm.",
             180000, "Mỹ phẩm",
             ["Không cần rửa lại", "Không cồn", "500ml dùng được 3-4 tháng", "Làm sạch cả waterproof makeup", "pH cân bằng 5.5"]),
            ("Mặt nạ ngủ Sleeping Mask", "Mặt nạ ngủ cấp ẩm chuyên sâu, chứa ceramide và squalane. Thoa trước khi ngủ, sáng dậy da mềm mịn, căng bóng.",
             290000, "Mỹ phẩm",
             ["Cấp ẩm 24h", "Chứa ceramide phục hồi", "Squalane khóa ẩm", "Thoa trước khi ngủ", "Không cần rửa lại"]),
        ]
        for i, (name, desc, price, cat, highlights) in enumerate(products):
            await db.execute(text("""
            INSERT INTO products (shop_id, name, description, price, currency, highlights,
                                  category, is_active)
            VALUES (1, :name, :desc, :price, 'VND',
                    :highlights,
                    :cat, true)
            """), {"name": name, "desc": desc, "price": price, "cat": cat, "highlights": highlights})

        # 6. Twenty script samples across 5 industries
        script_samples = [
            # Mỹ phẩm - 4 scripts
            ("Mỹ phẩm", "thân thiện", "Giới thiệu kem chống nắng cho mùa hè",
             """Xin chào các chị em! Hôm nay mình giới thiệu đến các chị em sản phẩm mà mình dùng suốt mùa hè luôn nè - Kem chống nắng UV Shield SPF50+.

Các chị em biết không, nắng mùa hè ở Việt Nam mình khắc nghiệt lắm, không bảo vệ da là thâm nám liền à. Kem này SPF50+ PA++++ nha, chống cả UVA lẫn UVB luôn.

Điểm mình thích nhất là thoa lên không nhờn, không bết, lớp nền makeup vẫn mịn đẹp. Có chiết xuất centella nữa nên da nhạy cảm dùng cũng ok nha.

Giá chỉ 350k thôi mà dùng được cả mặt cả body luôn, tiết kiệm lắm! Ai muốn lấy thì comment "chống nắng" nha các chị em!""",
             5, ["chống nắng", "mùa hè", "SPF50"]),

            ("Mỹ phẩm", "năng động", "Flash sale serum vitamin C",
             """Yo yo yo! Mọi người ơi deal hot nhất hôm nay đây rồi!

Serum Vitamin C 20% - sản phẩm mà beauty blogger nào cũng review, hôm nay flash sale giảm 30% luôn nha!

20% Vitamin C nguyên chất, combo Niacinamide 5% + Hyaluronic Acid. Dùng 4 tuần là thâm nám bay sạch luôn á!

Bình thường 480k, hôm nay chỉ còn 336k thôi nha! Số lượng có hạn, ai nhanh tay thì comment "serum" để mình chốt đơn liền!

3... 2... 1... Bắt đầu chốt!""",
             4, ["flash sale", "vitamin C", "serum"]),

            ("Mỹ phẩm", "chuyên nghiệp", "Review chi tiết son môi lì",
             """Kính chào quý khách! Hôm nay tôi xin được giới thiệu đến quý khách dòng son môi lì Velvet Matte - sản phẩm đang được rất nhiều quý khách yêu thích.

Về thành phần, son được sản xuất theo tiêu chuẩn quốc tế, không chứa chì, không paraben, an toàn tuyệt đối. Đặc biệt có thành phần dưỡng ẩm nhẹ giúp môi không bị khô.

Về bảng màu, chúng tôi có 12 shade được nghiên cứu riêng cho tone da người Việt Nam, từ hồng nude nhẹ nhàng đến đỏ trầm sang trọng.

Khả năng giữ màu đến 8 tiếng, quý khách có thể yên tâm makeup buổi sáng mà không cần touch up cả ngày.

Mức giá 220.000đ cho chất lượng như vậy, tôi tin là rất hợp lý. Quý khách quan tâm shade nào xin hãy comment bên dưới ạ.""",
             5, ["son môi", "review", "chi tiết"]),

            ("Mỹ phẩm", "hài hước", "Tẩy trang cuối ngày",
             """Alô alô! Ai cuối ngày mệt muốn xỉu mà vẫn phải tẩy trang giơ tay lên nào!

Mình biết cái cảm giác đó, về nhà chỉ muốn lăn ra ngủ, nhưng không tẩy trang thì sáng mai da kêu cứu luôn!

Giải pháp đây: Micellar Water 500ml - lau một phát sạch bong, không cần rửa lại luôn nha! Lười level max cũng handle được!

Không cồn nên da nhạy cảm dùng thoải mái. pH 5.5 cân bằng hoàn hảo. Mà 500ml to đùng dùng cả 3-4 tháng, chia ra mỗi ngày có mấy trăm đồng à!

180k mà được 4 tháng tuổi trẻ, đầu tư có lời quá đi! Comment "tẩy trang" để chốt nha!""",
             5, ["tẩy trang", "hài hước", "tiết kiệm"]),

            # Thời trang - 4 scripts
            ("Thời trang", "thân thiện", "Giới thiệu bộ sưu tập áo hè",
             """Chào các chị em yêu! Hôm nay mình lên đồ mới cho các chị em nè - Bộ sưu tập áo hè 2026!

Năm nay trend là vải linen thoáng mát nha các chị em. Mình chọn toàn chất vải cao cấp, mặc mát rượi giữa cái nóng Sài Gòn luôn.

Form áo rộng vừa phải, che được bụng mỡ mà vẫn thanh lịch nha. Các chị em mặc đi làm hay đi chơi đều ok hết!

Bảng màu năm nay mình có: trắng kem, xanh pastel, hồng phấn, và xám khói. Màu nào cũng dễ phối luôn!

Giá chỉ từ 299k, đặt hàng hôm nay free ship nội thành nha! Comment size + màu để mình tư vấn thêm ạ!""",
             4, ["áo hè", "linen", "thời trang"]),

            ("Thời trang", "năng động", "Livestream giày sneaker mới",
             """What's up mọi người! Drop giày mới cực hot đây!

Sneaker Cloud Walker - nhẹ như mây, êm như đệm, phong cách như idol!

Đế cloudfoam thế hệ mới, chạy nhảy cả ngày chân vẫn thấy phê. Upper mesh thoáng khí, đi giữa trưa nắng chân vẫn khô thoáng.

5 màu siêu clean: trắng full, đen full, xám xi-măng, navy, và limited pastel pink.

Size từ 36-44, unisex luôn nha! Giá retail 890k, live hôm nay chỉ 690k! Giảm thêm 50k cho ai mua đôi thứ 2!

Comment size + màu là mình chốt liền! Giao hàng 2-3 ngày thôi!""",
             4, ["sneaker", "giày", "drop mới"]),

            ("Thời trang", "chuyên nghiệp", "Bộ vest công sở nam",
             """Kính chào quý khách! Hôm nay chúng tôi xin giới thiệu dòng vest công sở premium dành cho quý ông.

Chất liệu wool blend nhập khẩu Ý, co giãn nhẹ giúp quý khách thoải mái vận động cả ngày mà vest vẫn giữ form hoàn hảo.

Chúng tôi may đo theo 6 size chuẩn body người Việt, đảm bảo vừa vặn mà không cần chỉnh sửa nhiều. Đường may kỹ thuật, nút áo cao cấp, lót trong bằng lụa.

Có 3 phiên bản: Navy Classic, Charcoal Grey, và Black Formal. Mỗi bộ đều kèm vest + quần.

Mức đầu tư 1.890.000đ cho bộ vest mặc được hàng năm trời. Quý khách cần tư vấn size xin comment chiều cao và cân nặng ạ.""",
             5, ["vest", "công sở", "premium"]),

            ("Thời trang", "hài hước", "Đồ ngủ pijama cute",
             """Haha ai mà ngủ mặc đồ cũ giơ tay lên nào! Có mình thôi hả? Thôi hết rồi nha!

Pijama lụa cao cấp - mặc ngủ đẹp đến mức đi ra ngoài cũng được luôn á!

Vải lụa mềm mịn, mát lạnh, nằm điều hòa 25 độ là sướng phải biết! Mà giặt máy thoải mái, không sợ nhăn, không sợ phai màu.

Hoa văn cute phô mai que, mà thanh lịch nữa nha! Có cả set đôi cho cặp đôi luôn, tặng người yêu là ghi điểm max!

Set 1 người 350k, set đôi 599k tiết kiệm 100k! Comment "pijama" kèm size S/M/L/XL nha!""",
             4, ["pijama", "đồ ngủ", "lụa"]),

            # Đồ gia dụng - 4 scripts
            ("Đồ gia dụng", "thân thiện", "Nồi chiên không dầu",
             """Chào mọi người! Hôm nay mình giới thiệu người bạn thân trong bếp của mình nè - Nồi chiên không dầu 5.5L!

Các chị em biết không, từ ngày có em nó, mình nấu ăn nhanh gấp đôi mà healthy hơn nhiều luôn. Khoai tây chiên giòn rụm mà không cần giọt dầu nào!

Dung tích 5.5L đủ cho cả gia đình 4-5 người ăn thoải mái. Có 8 chế độ nấu sẵn, chỉ cần bấm nút là xong!

Mặt trong phủ chống dính, rửa xong lau khô là sạch bong. Tiết kiệm điện hơn lò nướng truyền thống đến 70%!

Giá hôm nay chỉ 1.290k, tặng kèm sách 50 công thức nha! Comment "nồi" để mình gửi link đặt hàng ạ!""",
             5, ["nồi chiên không dầu", "healthy", "gia dụng"]),

            ("Đồ gia dụng", "năng động", "Robot hút bụi thông minh",
             """Tin hot cho team lười dọn nhà! Robot hút bụi AI Navigation đã về kho!

Bé này thông minh lắm nha - mapping nhà bằng LiDAR, tự tránh vật cản, tự về dock sạc. Mình cài lịch cho nó dọn lúc đi làm, về nhà là sạch rồi!

Lực hút 4000Pa, hút được cả lông thú cưng. Có thêm chế độ lau ướt luôn, 2 trong 1 tiện quá trời!

Pin 5200mAh chạy liên tục 180 phút, căn hộ 100m2 dọn 2 lượt vẫn dư pin!

Giá 4.990k nghe hơi mắc nhưng tính ra mỗi ngày có 14k thôi, rẻ hơn thuê người dọn nhiều! Comment "robot" để chốt nhé!""",
             4, ["robot hút bụi", "smart home", "AI"]),

            ("Đồ gia dụng", "chuyên nghiệp", "Máy lọc nước RO",
             """Kính chào quý khách! Sức khỏe gia đình bắt đầu từ nguồn nước sạch. Hôm nay chúng tôi giới thiệu Máy lọc nước RO 10 cấp lọc.

Hệ thống 10 cấp lọc bao gồm: lọc thô, than hoạt tính, màng RO 0.0001 micron, khoáng hóa, và diệt khuẩn UV. Loại bỏ 99.99% vi khuẩn và kim loại nặng.

Công suất lọc 10L/giờ, tích hợp bình chứa 8L, đáp ứng nhu cầu gia đình 4-6 người.

Lõi lọc thay mỗi 12 tháng, chi phí thay lõi chỉ 500.000đ/năm. Bảo hành motor 5 năm.

Đầu tư 5.990.000đ cho sức khỏe cả gia đình, lắp đặt miễn phí tại nhà. Quý khách quan tâm xin comment "lọc nước" ạ.""",
             5, ["máy lọc nước", "RO", "sức khỏe"]),

            ("Đồ gia dụng", "hài hước", "Quạt điều hòa mini",
             """Nóng quá trời nóng! Ai đang tan chảy như mình giơ tay lên!

Giải cứu đây: Quạt điều hòa mini - mát như điều hòa mà tiền điện bằng quạt!

Nguyên lý bay hơi nước, đổ nước đá vào là phòng mát rượi trong 5 phút. Tiền điện mỗi tháng chưa đến 50k, trong khi điều hòa tốn 500-700k!

Nhỏ gọn di chuyển được, phòng ngủ xong kéo ra phòng khách. Không cần thợ lắp đặt, cắm điện là chạy!

Giá chỉ 890k, mua 2 cái giảm thêm 100k! Mùa hè mà không có em này thì sống sao nổi! Comment "quạt" là mình ship liền!""",
             4, ["quạt điều hòa", "mùa hè", "tiết kiệm điện"]),

            # Thực phẩm chức năng - 4 scripts
            ("Thực phẩm chức năng", "thân thiện", "Collagen dạng nước",
             """Chào các chị em! Ai muốn da đẹp từ bên trong thì đọc bình luận nha!

Hôm nay mình giới thiệu Collagen nước 10.000mg - sản phẩm mình uống đều đặn 3 tháng nay rồi và da thay đổi thật sự luôn!

Mỗi chai chứa 10.000mg collagen peptide thủy phân, hấp thu nhanh gấp 3 lần dạng viên. Thêm vitamin C và biotin giúp da sáng, tóc mượt, móng chắc.

Vị dâu tây nhẹ, uống dễ lắm, không tanh. Mỗi ngày 1 chai trước khi ngủ, sáng dậy da mềm mịn thấy rõ!

Hộp 30 chai giá 890k, uống được 1 tháng. Mua 2 hộp giảm 10% nha! Comment "collagen" để mình tư vấn thêm ạ!""",
             5, ["collagen", "làm đẹp", "da"]),

            ("Thực phẩm chức năng", "năng động", "Whey protein tập gym",
             """Gym bro gym sis ơi! Whey Protein Isolate 90% đã về hàng!

Mỗi scoop 30g chứa 27g protein, chỉ 1g carb và 0.5g fat. Clean macro cực kỳ!

Hòa tan nhanh, không vón cục, không đầy bụng. 3 vị: Chocolate, Vanilla, và Cookies & Cream - vị nào cũng ngon!

Nguồn whey nhập khẩu New Zealand, kiểm nghiệm không chứa chất cấm. Dùng an tâm cho cả vận động viên thi đấu!

Hộp 1kg giá 790k, 33 lần dùng, tính ra mỗi lần chưa đến 24k - rẻ hơn ly trà sữa! Comment "whey" + vị muốn mua nhé!""",
             4, ["whey protein", "gym", "fitness"]),

            ("Thực phẩm chức năng", "chuyên nghiệp", "Omega-3 dầu cá",
             """Kính chào quý khách! Hôm nay chúng tôi xin giới thiệu sản phẩm Omega-3 Fish Oil 1000mg - sản phẩm bổ sung thiết yếu cho sức khỏe tim mạch và trí não.

Mỗi viên chứa 1000mg dầu cá tinh khiết, trong đó EPA 360mg và DHA 240mg - hàm lượng cao nhất phân khúc.

Nguồn nguyên liệu từ cá biển sâu vùng Bắc Âu, qua quy trình tinh lọc phân tử loại bỏ kim loại nặng và tạp chất.

Nghiên cứu lâm sàng cho thấy bổ sung Omega-3 đều đặn giúp giảm 25% nguy cơ tim mạch, cải thiện trí nhớ và thị lực.

Hộp 120 viên dùng 4 tháng, giá 590.000đ. Quý khách comment "omega" để được tư vấn chi tiết ạ.""",
             5, ["omega-3", "tim mạch", "sức khỏe"]),

            ("Thực phẩm chức năng", "hài hước", "Vitamin tổng hợp",
             """Ai hay quên uống vitamin giơ tay! À mà giơ tay xong nhớ uống nha!

Vitamin tổng hợp Daily Multi - 1 viên là đủ 23 vitamin và khoáng chất cần thiết. Không cần nhớ uống 5-6 loại khác nhau nữa!

Viên nhỏ dễ nuốt, không tanh, không buồn nôn. Uống sau bữa sáng là xong, đơn giản như đánh răng!

Có đủ từ A đến Zinc: Vitamin A, B complex, C, D3, E, K2, sắt, kẽm, canxi... Mua 1 chai bằng mua cả tiệm thuốc mini!

Chai 90 viên dùng 3 tháng, giá 390k. Chia ra mỗi ngày hơn 4k - rẻ hơn ly cà phê mà khỏe cả người! Comment "vitamin" nha!""",
             4, ["vitamin", "tổng hợp", "sức khỏe"]),

            # Mẹ và bé - 4 scripts
            ("Mẹ và bé", "thân thiện", "Sữa bột cho bé 1-3 tuổi",
             """Chào các mẹ yêu! Hôm nay mình chia sẻ về sữa bột mà bé nhà mình đang uống nè - Sữa Gold Grow 1-3 tuổi!

Công thức có DHA và ARA giúp phát triển trí não, canxi nano dễ hấp thu giúp bé cao lớn. Thêm chất xơ prebiotic GOS/FOS giúp bé tiêu hóa tốt, không bị táo bón nha các mẹ!

Vị sữa thanh nhẹ, bé nhà mình khó ăn lắm mà uống hết sạch luôn! Pha cũng dễ, tan nhanh không vón cục.

Hộp 800g giá 420k, dùng được khoảng 3 tuần. Mua thùng 6 hộp giảm 15% và free ship!

Các mẹ muốn tư vấn thêm thì comment "sữa" + tuổi bé nha, mình tư vấn cho phù hợp ạ!""",
             5, ["sữa bột", "trẻ em", "dinh dưỡng"]),

            ("Mẹ và bé", "năng động", "Bỉm dán cho bé sơ sinh",
             """Các mẹ bỉm sữa ơi! Deal bỉm khủng nhất tháng đây rồi!

Bỉm dán Softie Newborn - siêu mỏng chỉ 3mm mà thấm hút cực đỉnh! Bé mặc cả đêm vẫn khô thoáng, không hăm đỏ!

Bề mặt cotton organic, mềm mại như đắp lụa cho bé. Đai co giãn 360 độ, bé vận động thoải mái không bị hằn!

Size NB cho bé dưới 5kg, size S cho 4-8kg. Có indicator đổi màu báo thay bỉm luôn, tiện cho mẹ bận rộn!

Thùng 108 miếng chỉ 350k! Mua 2 thùng tặng 1 gói khăn ướt! Comment "bỉm" + size bé nha!""",
             4, ["bỉm", "sơ sinh", "mẹ và bé"]),

            ("Mẹ và bé", "chuyên nghiệp", "Ghế ăn dặm cho bé",
             """Kính chào quý phụ huynh! Giai đoạn ăn dặm là bước ngoặt quan trọng trong sự phát triển của bé. Hôm nay chúng tôi giới thiệu Ghế ăn dặm đa năng 3 trong 1.

Ghế được thiết kế theo tiêu chuẩn an toàn châu Âu EN 14988, chịu lực đến 15kg. Đai an toàn 5 điểm giữ bé chắc chắn trong mọi tư thế.

3 chế độ sử dụng: ghế cao cho bé ăn cùng bàn gia đình, ghế thấp để bé tự ăn, và ghế bệt cho bé chơi. Điều chỉnh chiều cao 7 nấc, khay ăn tháo rời rửa máy được.

Chất liệu nhựa PP an toàn thực phẩm, không BPA. Đệm ngồi bọc PU dễ lau chùi.

Mức đầu tư 1.290.000đ, sử dụng được từ 6 tháng đến 3 tuổi. Quý khách comment "ghế ăn" để được tư vấn ạ.""",
             5, ["ghế ăn dặm", "an toàn", "đa năng"]),

            ("Mẹ và bé", "hài hước", "Đồ chơi xếp hình gỗ",
             """Bé nhà ai phá đồ chơi như cơm bữa giơ tay lên! Yên tâm, có giải pháp rồi!

Bộ xếp hình gỗ 100 chi tiết - bền đến mức con phá mấy cũng không hỏng! Gỗ thông tự nhiên, sơn nước an toàn, bé cắn cũng không sao!

Vừa chơi vừa học: nhận biết màu sắc, hình khối, rèn vận động tinh. Mấy mẹ mua về là có thời gian rảnh uống trà sữa luôn nha, bé mê chơi quên cả quấy!

100 chi tiết đủ xây cả thành phố mini. Kèm sách hướng dẫn 20 mô hình, từ dễ đến khó.

Giá 290k cho bộ 100 chi tiết, so với mấy đồ chơi nhựa chơi 2 ngày hỏng thì đây là deal ngon! Comment "xếp hình" + tuổi bé nha!""",
             4, ["đồ chơi", "xếp hình gỗ", "giáo dục"]),
        ]

        for cat, style, title, content, score, tags in script_samples:
            await db.execute(text("""
            INSERT INTO script_samples (category, persona_style, title, content,
                                        quality_score, tags, created_by)
            VALUES (:cat, :style, :title, :content, :score,
                    :tags, 'system')
            """), {"cat": cat, "style": style, "title": title, "content": content, "score": score, "tags": tags})

        # Reset sequences
        await db.execute(text("SELECT setval('users_id_seq', (SELECT max(id) FROM users))"))
        await db.execute(text("SELECT setval('shops_id_seq', (SELECT max(id) FROM shops))"))

        await db.commit()
        print("Seed completed: 1 user, 1 shop, 4 personas, 5 products, 20 script samples")


if __name__ == "__main__":
    asyncio.run(seed())
