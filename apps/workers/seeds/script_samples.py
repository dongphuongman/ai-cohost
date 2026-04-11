"""Seed data: 20 Vietnamese livestream script samples for few-shot learning.

Usage:
    cd apps/workers && python -m seeds.script_samples
"""

import logging
from datetime import datetime, timezone

import google.generativeai as genai
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from config import settings

logger = logging.getLogger(__name__)

SAMPLES = [
    # --- MY PHAM (4 samples) ---
    {
        "category": "mỹ phẩm",
        "persona_style": "thân thiện",
        "title": "Kem chống nắng SPF50 - 10 phút",
        "quality_score": 5,
        "content": """# Mở đầu

Chào cả nhà mình ơi! Lại là chị Linh đây, hôm nay chị quay lại với mọi người với một sản phẩm mà chị tin chắc là ai cũng cần, đặc biệt là mùa nắng nóng thế này. Mọi người nhớ ấn follow và like cho chị nhé, để không bỏ lỡ những deal hot sau này!

# Giới thiệu sản phẩm

Hôm nay chị giới thiệu cho cả nhà kem chống nắng SPF50 PA++++. Nói thật với mọi người, chị đã thử qua hơn 20 loại kem chống nắng rồi, mà cái này là cái chị ưng nhất.

Thứ nhất, kết cấu nó lỏng nhẹ lắm, thoa lên da thấm trong 30 giây thôi. Mọi người biết không, nhiều kem chống nắng thoa lên trắng bệch, nhờn rít, nhưng cái này không hề. Da dầu mụn dùng cũng ok luôn.

Thứ hai, SPF50 PA++++ nghĩa là bảo vệ tối đa luôn ạ. Nắng Sài Gòn 40 độ mà thoa cái này ra đường thoải mái. Chị đã test 1 tuần liền, da không bị sạm chút nào.

Thứ ba, sản phẩm có thành phần an toàn, không cồn, không hương liệu, da nhạy cảm dùng được ạ.

# Xử lý phản đối

Chị biết nhiều bạn sẽ hỏi: "Chị ơi, giá hơi cao không?" Mọi người nghĩ xem, một tuýp dùng được 2-3 tháng, tính ra mỗi ngày chưa đến 4 nghìn đồng. Bằng cốc trà đá thôi mà bảo vệ da cả ngày, đáng lắm mọi người ơi!

Còn bạn nào hỏi "da dầu dùng có bị bít tắc không?" — Không ạ, sản phẩm non-comedogenic, tức là không gây mụn ạ.

# Call to Action

Nhanh tay lên mọi người ơi! Hôm nay chị để deal đặc biệt chỉ trong live này thôi. Comment "MUA" để chị gửi link nhé! Ai nhanh tay thì có quà tặng kèm sữa rửa mặt mini size nữa!

Số lượng khuyến mãi có hạn, chỉ còn 50 set thôi nha!

# Kết thúc

Cảm ơn cả nhà đã ở lại với chị Linh hôm nay! Nhớ follow để tối mai 8h chị lại live tiếp với bộ skincare mùa hè nhé. Yêu cả nhà!""",
    },
    {
        "category": "mỹ phẩm",
        "persona_style": "chuyên nghiệp",
        "title": "Serum Vitamin C - 10 phút",
        "quality_score": 5,
        "content": """# Mở đầu

Xin chào tất cả mọi người, cảm ơn các bạn đã tham gia buổi live hôm nay. Mình là Hà, hôm nay mình sẽ giới thiệu đến các bạn một sản phẩm skincare mà mình rất tâm đắc. Trước khi bắt đầu, các bạn nhớ nhấn theo dõi để nhận thông báo cho những buổi live tiếp theo nhé.

# Giới thiệu sản phẩm

Sản phẩm hôm nay là Serum Vitamin C 15% — một sản phẩm được đông đảo beauty blogger và bác sĩ da liễu khuyên dùng.

Về thành phần: Sản phẩm chứa L-Ascorbic Acid ở nồng độ 15%, kết hợp với Vitamin E và Ferulic Acid. Bộ ba này đã được nghiên cứu khoa học chứng minh là tăng hiệu quả chống oxy hóa lên gấp 8 lần so với dùng Vitamin C đơn lẻ.

Về công dụng: Sau 4 tuần sử dụng đều đặn, bạn sẽ thấy da sáng đều màu hơn, các vết thâm mờ dần, và da có độ căng bóng tự nhiên. Mình đã sử dụng được 3 tháng và kết quả thực sự rất ấn tượng.

Về cách dùng: Rất đơn giản. Sau bước toner, các bạn lấy 3-4 giọt serum, ấn nhẹ lên da. Dùng vào buổi sáng, nhớ thoa kem chống nắng sau đó.

# Xử lý phản đối

Nhiều bạn lo ngại Vitamin C sẽ gây kích ứng. Đúng là với da nhạy cảm, các bạn nên thử trước ở vùng sau tai. Tuy nhiên, nồng độ 15% là mức an toàn cho hầu hết loại da.

Về bảo quản: sản phẩm nên để nơi thoáng mát, tránh ánh nắng trực tiếp. Sau khi mở nắp, sử dụng trong vòng 3 tháng để đảm bảo hiệu quả.

# Call to Action

Hôm nay shop có chương trình ưu đãi đặc biệt cho sản phẩm này. Các bạn comment "SERUM" để nhận link đặt hàng với giá tốt nhất. Chỉ áp dụng trong buổi live này thôi nhé.

# Kết thúc

Cảm ơn tất cả các bạn đã dành thời gian theo dõi. Hẹn gặp lại các bạn vào thứ Năm tuần sau, mình sẽ review thêm sản phẩm mới. Chúc các bạn buổi tối vui vẻ!""",
    },
    {
        "category": "mỹ phẩm",
        "persona_style": "vui vẻ",
        "title": "Son môi lì - 5 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Ê ê ê, ai ở đây nè! Chào mừng mọi người đến với buổi live của Trang nè! Hôm nay mình có một sản phẩm siêu xịn muốn khoe với mọi người luôn. Like và share cho mình nha, share nhiều mình tặng quà luôn!

# Giới thiệu sản phẩm

Đố mọi người biết hôm nay mình khoe gì nè? Đúng rồi — son môi lì siêu mịn! Mình đang tô màu này nè, mọi người thấy đẹp không? Tô lên môi mịn lắm luôn, không bị khô, không bị vón cục.

Bảng màu có 12 màu nha mọi người, từ màu nude nhẹ nhàng đi làm, đến màu đỏ cam cháy sàn live luôn! Mình thích nhất màu số 05 — đỏ đất, tô lên da nào cũng hợp.

Điểm hay nhất là son này bám màu cực kỳ tốt nha. Mình tô từ sáng đến giờ, ăn phở xong, uống trà sữa xong, màu vẫn còn nguyên. Ai mà hay bị son trôi thì thử cái này đi, sẽ bất ngờ luôn!

# Xử lý phản đối

"Trang ơi, son lì có bị khô môi không?" — Mình hiểu lo lắng này, nhưng son này có thành phần dưỡng ẩm luôn rồi nha. Tất nhiên là mình vẫn khuyên các bạn dùng lip balm trước khi tô thì sẽ mịn hơn nữa.

# Call to Action

Giá chỉ có 199k thôi mọi người ơi! Mua 2 cây giảm thêm 10% nha. Comment màu mình thích kèm SĐT, mình inbox link liền! Nhanh tay lên, hàng bay nhanh lắm!

# Kết thúc

Ok vậy là hết rồi nha mọi người! Cảm ơn ai đã ở lại xem live. Mai 7h tối mình live tiếp nha, sẽ có unbox hàng mới cực hot. Bye bye!""",
    },
    {
        "category": "mỹ phẩm",
        "persona_style": "thân thiện",
        "title": "Sữa rửa mặt amino acid - 10 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Chào mọi người nha, mình là Mai, cảm ơn cả nhà đã vào live tối nay. Ai mới vào thì nhớ bấm follow để không bỏ lỡ các buổi live sau nhé. Hôm nay mình giới thiệu một sản phẩm mà mình rất yêu thích.

# Giới thiệu sản phẩm

Đây là sữa rửa mặt amino acid, dạng gel trong suốt, mùi thơm rất nhẹ nhàng. Mình dùng sản phẩm này được 2 tháng rồi và thấy da mình cải thiện rõ rệt.

Trước đây mình hay dùng sữa rửa mặt tạo bọt mạnh, rửa xong da căng khô, có khi còn bị bong tróc. Nhưng từ khi chuyển sang dùng cái này, da mình mềm mại hẳn, lỗ chân lông cũng nhỏ hơn.

Thành phần amino acid rất dịu nhẹ, pH 5.5 cân bằng với da. Các bạn da nhạy cảm, da mụn, hay thậm chí da sau peel đều dùng được ạ.

Cách dùng rất đơn giản: lấy 1 lượng bằng hạt đậu, tạo bọt với nước rồi massage nhẹ lên mặt 30 giây, sau đó rửa sạch. Sáng tối đều dùng được.

# Xử lý phản đối

Nhiều bạn hỏi: "Sữa rửa mặt dịu nhẹ vậy có sạch không?" Câu trả lời là có ạ! Amino acid tuy dịu nhẹ nhưng vẫn loại bỏ bụi bẩn, dầu thừa hiệu quả. Nếu các bạn trang điểm nặng thì nên double cleanse — tẩy trang trước rồi rửa mặt sau.

# Call to Action

Giá gốc 250k nhưng hôm nay live chỉ 189k thôi mọi người ơi. Mua 2 tặng 1 bông rửa mặt konjac. Comment "SRM" để mình gửi link nha!

# Kết thúc

Cảm ơn cả nhà đã xem live với Mai hôm nay. Thứ Bảy tuần này mình sẽ live tiếp về routine skincare buổi tối. Hẹn gặp lại, chúc mọi người ngủ ngon!""",
    },

    # --- THOI TRANG (4 samples) ---
    {
        "category": "thời trang",
        "persona_style": "vui vẻ",
        "title": "Váy hoa mùa hè - 5 phút",
        "quality_score": 5,
        "content": """# Mở đầu

Hello hello mọi người ơi! Ai yêu váy đẹp thì vào đây nè! Hôm nay mình có váy mới về siêu xinh, mặc vào là chuẩn gái Hàn luôn! Like nhiều cho mình nha, like 500 mình sale sốc luôn!

# Giới thiệu sản phẩm

Mọi người nhìn nè, váy hoa nhí này xinh không? Mình đang mặc size M nè, cao mình 1m60, 52 ký, mặc vừa đẹp luôn.

Chất vải là voan lụa nha, mặc mát lắm, không bí, không nhăn. Mùa hè nóng 38 độ mặc váy này ra đường vẫn thoải mái.

Váy có dây rút eo nha mọi người, nên bạn nào gầy hay mập đều mặc được hết. Size S cho bạn 40-48 ký, M cho 48-55, L cho 55-62. Dài đến ngang gối, vừa kín đáo vừa nữ tính.

Bảng màu có 4 màu: trắng hoa nhí, xanh hoa nhí, vàng kem, và hồng pastel. Mình thấy màu nào cũng đẹp hết!

# Xử lý phản đối

"Vải mỏng có bị lộ không?" — Không nha mọi người, váy có lớp lót bên trong rồi, yên tâm mặc nhé. "Giặt máy được không?" — Được luôn, nhưng nên bỏ túi giặt nha để giữ form.

# Call to Action

Giá váy chỉ 289k thôi nha! Mua 2 cái giảm 50k. Comment "VAY + SIZE + MAU" là mình inbox link liền! Đừng bỏ lỡ, hàng về ít lắm!

# Kết thúc

Ok cảm ơn mọi người nha! Mình còn nhiều mẫu mới nữa, tối mai 8h live tiếp nha. Bye bye, yêu mọi người!""",
    },
    {
        "category": "thời trang",
        "persona_style": "chuyên nghiệp",
        "title": "Áo sơ mi công sở - 10 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Xin chào các chị em, cảm ơn các bạn đã tham gia buổi live hôm nay. Mình là Thảo, hôm nay mình sẽ giới thiệu bộ sưu tập áo sơ mi công sở mới nhất. Các bạn nhớ follow shop để cập nhật hàng mới nhé.

# Giới thiệu sản phẩm

Bộ sưu tập lần này gồm 6 mẫu áo sơ mi, thiết kế tối giản nhưng rất thanh lịch, phù hợp cho môi trường công sở.

Mẫu đầu tiên mình đang mặc đây — sơ mi trắng cổ V nhỏ. Chất lụa trơn, mặc không bị nhăn sau cả ngày làm việc. Thiết kế cổ V vừa phải, đủ thanh lịch cho meeting mà vẫn thoải mái.

Mẫu thứ hai là sơ mi xanh pastel, cổ đức. Các bạn thấy màu này rất dễ phối không? Mặc với quần tây đen, quần khaki, hoặc chân váy bút chì đều đẹp.

Điểm đặc biệt của tất cả áo trong BST này là chất vải có thành phần co giãn 5%, nên các bạn cử động thoải mái, không bị bó khi ngồi máy tính cả ngày.

Size từ S đến XL, bảng size rất chuẩn. Mình 1m63, 54kg, mặc M vừa đẹp.

# Xử lý phản đối

"Vải lụa có bị mồ hôi lem không?" — BST này dùng lụa pha polyester chống lem, nên các bạn yên tâm. "Có cần ủi không?" — Gần như không cần, treo lên là phẳng.

# Call to Action

Giá mỗi áo 349k, combo 3 áo chỉ 899k — tiết kiệm gần 150k. Comment "AOCONGSO + SIZE" để mình gửi link. Miễn phí vận chuyển cho đơn từ 2 áo.

# Kết thúc

Cảm ơn các bạn đã theo dõi. Tuần sau mình sẽ live BST quần công sở matching. Chúc các bạn một tuần làm việc hiệu quả!""",
    },
    {
        "category": "thời trang",
        "persona_style": "thân thiện",
        "title": "Đồ bộ mặc nhà - 5 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Chào cả nhà, mình là Ngọc nè! Ai đang tìm đồ bộ mặc nhà mềm mại thì đúng live rồi nha. Like và share giúp mình nhé!

# Giới thiệu sản phẩm

Hôm nay mình giới thiệu bộ đồ mặc nhà cotton 100%. Mình đang mặc nè, mọi người thấy thoải mái không? Chất cotton dày dặn nhưng mát, thấm mồ hôi cực tốt.

Áo cổ tròn, tay ngắn, quần dài ống rộng có chun co giãn. Mặc ngủ hay mặc ra ngoài đi siêu thị đều được, trông vẫn gọn gàng.

Có 8 màu nha: đen, ghi, be, xanh navy, hồng nhạt, tím lavender, trắng, và xanh rêu. Mỗi màu đều có họa tiết sọc nhỏ rất tinh tế.

# Xử lý phản đối

"Cotton có bị co rút khi giặt không?" — Mình đã giặt 10 lần rồi, không co rút nha. Nhớ giặt nước lạnh hoặc ấm, không dùng nước nóng là được.

# Call to Action

Giá chỉ 199k/bộ, mua 3 bộ giảm còn 159k/bộ. Comment "DOBO + SIZE + MAU" nha. Free ship cho đơn từ 2 bộ!

# Kết thúc

Cảm ơn mọi người! Tối mai mình live tiếp đồ bộ bông cho mùa lạnh nha. Bye cả nhà!""",
    },
    {
        "category": "thời trang",
        "persona_style": "vui vẻ",
        "title": "Giày sneaker nữ - 10 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Yo yo mọi người! Ai thích sneaker thì zô đây! Hôm nay mình unbox và review giày sneaker siêu hot nè. Follow mình đi, hứa không hối hận!

# Giới thiệu sản phẩm

Đây nè, sneaker trắng basic nhưng cực kỳ chất lượng. Mình đi thử 1 tuần rồi, đôi giày này mình cho 10/10 luôn.

Đế cao 3cm nha, vừa đủ tôn dáng mà đi cả ngày không mỏi chân. Mình đi bộ 5km còn không đau chân, ai hay đi nhiều thì nên mua luôn.

Chất liệu da tổng hợp cao cấp, nhìn y chang da thật luôn. Lau bằng khăn ướt là sạch, không cần chăm sóc phức tạp.

Size từ 35-40, size chuẩn nha. Chân mình 37, đi vừa khít. Ai chân rộng thì lên 1 size nha.

Có 3 màu: trắng full, trắng đế be, và trắng viền đen. Màu nào cũng dễ phối đồ hết!

# Xử lý phản đối

"Giày trắng có bị ố vàng không?" — Không nha, chất liệu này chống ố. "Đi mưa được không?" — Được, nhưng nên lau khô sau khi dính nước nhiều.

# Call to Action

Deal live hôm nay 399k thôi nha! Giá gốc 550k luôn. Comment "GIAY + SIZE" mình inbox link. Mua kèm vớ chống hôi chân chỉ thêm 29k!

# Kết thúc

Vậy thôi nha mọi người! Hẹn gặp lại thứ 7 mình live giày cao gót công sở. Love you all!""",
    },

    # --- GIA DUNG (4 samples) ---
    {
        "category": "gia dụng",
        "persona_style": "thân thiện",
        "title": "Nồi chiên không dầu - 10 phút",
        "quality_score": 5,
        "content": """# Mở đầu

Chào mọi người ạ! Mình là Huyền, chào mừng cả nhà đến với buổi live hôm nay. Ai đang muốn nấu ăn healthy mà lười vào bếp thì video này dành cho bạn! Nhớ like và follow mình nha!

# Giới thiệu sản phẩm

Hôm nay mình giới thiệu nồi chiên không dầu dung tích 5.5 lít — size này vừa đủ cho gia đình 3-4 người ạ.

Mình sẽ demo luôn nha. Đây là cánh gà — mình chỉ ướp gia vị, không cần cho thêm dầu. Cho vào nồi, chỉnh 180 độ, 20 phút. Trong lúc chờ mình giới thiệu thêm nhé.

Nồi có 8 chế độ nấu sẵn: khoai tây chiên, gà, cá, rau, bánh, sấy khô, hâm nóng, và tự chỉnh. Mỗi chế độ đã cài sẵn nhiệt độ và thời gian phù hợp, các bạn chỉ cần nhấn nút.

Lòng nồi phủ chống dính ceramic, rất dễ vệ sinh. Mình chỉ cần lau bằng khăn ẩm là sạch, không cần cọ rửa nhiều.

Ôi, mọi người nhìn nè — cánh gà chín rồi! Vàng đều, giòn tan, mà không giọt dầu nào. Mùi thơm phức luôn ạ!

# Xử lý phản đối

"Nồi chiên không dầu có thực sự giòn không?" — Mọi người thấy rồi đó, giòn y chang chiên dầu luôn ạ. Bí quyết là ướp chút baking powder.

"Tốn điện không?" — Nồi này công suất 1400W, chiên 20 phút tốn khoảng 800 đồng tiền điện thôi. Rẻ hơn nhiều so với dùng dầu.

# Call to Action

Giá live hôm nay chỉ 1.290.000đ, tặng kèm bộ phụ kiện 5 món. Comment "NOI" mình gửi link nhé! Free ship toàn quốc.

# Kết thúc

Cảm ơn cả nhà! Tuần sau mình sẽ live công thức nấu bằng nồi này nha. Hẹn gặp lại!""",
    },
    {
        "category": "gia dụng",
        "persona_style": "chuyên nghiệp",
        "title": "Máy hút bụi robot - 10 phút",
        "quality_score": 5,
        "content": """# Mở đầu

Xin chào các bạn, cảm ơn đã tham gia live stream hôm nay. Mình là Đức, hôm nay mình sẽ review chi tiết máy hút bụi robot thông minh. Nhấn theo dõi để không bỏ lỡ các review công nghệ tiếp theo nhé.

# Giới thiệu sản phẩm

Đây là robot hút bụi thế hệ mới, tích hợp cả hút bụi và lau nhà. Mình đã sử dụng 2 tháng và muốn chia sẻ trải nghiệm thực tế.

Về hiệu suất hút: lực hút 4000Pa, xử lý tốt bụi, lông thú cưng, và mảnh vụn thức ăn. Mình có 2 con mèo, máy hút sạch lông rất hiệu quả.

Về điều hướng: Sử dụng cảm biến LiDAR, máy quét và tạo bản đồ nhà trong lần chạy đầu tiên. Sau đó nó sẽ đi theo lộ trình tối ưu, không bị đâm vào đồ đạc.

Về pin: Dung lượng 5200mAh, chạy liên tục được 180 phút. Nhà mình 80m2, một lần chạy dư sức hút + lau xong toàn bộ.

Điều khiển qua app trên điện thoại: đặt lịch tự động, phân vùng dọn dẹp, điều chỉnh lực hút cho từng phòng.

# Xử lý phản đối

"Lau nhà có sạch thật không?" — Máy có bình nước 300ml với khăn microfiber, lau được vết bẩn nhẹ. Tất nhiên không thay thế được lau tay cho vết bẩn cứng đầu, nhưng cho duy trì hàng ngày thì rất tốt.

"Nhà có nhiều đồ đạc thì sao?" — Cảm biến LiDAR giúp máy tránh vật cản rất chính xác. Chỉ cần dọn dây điện và vật nhỏ dưới sàn.

# Call to Action

Giá sản phẩm 4.990.000đ, hôm nay giảm còn 3.990.000đ kèm 2 khăn lau dự phòng. Comment "ROBOT" để nhận link đặt hàng. Bảo hành 24 tháng chính hãng.

# Kết thúc

Cảm ơn các bạn đã theo dõi. Tuần sau mình sẽ review máy lọc không khí. Hẹn gặp lại!""",
    },
    {
        "category": "gia dụng",
        "persona_style": "vui vẻ",
        "title": "Bộ dao nhà bếp - 5 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Ê mọi người ơi vào đây! Hôm nay mình khoe bộ dao bếp xịn sò, cắt gì cũng ngọt luôn! Like mạnh tay đi nào!

# Giới thiệu sản phẩm

Bộ dao 5 món nha: dao chặt, dao thái, dao gọt, dao bào, và kéo cắt. Toàn bộ bằng thép không gỉ, sắc bén kinh hoàng!

Mình demo luôn nha — nhìn nè, cắt cà chua mỏng tang mà không bị dập. Dao thái cá thì một nhát ngọt lịm. Cán dao bằng gỗ, cầm rất chắc tay, không bị trơn khi tay ướt.

Bộ dao đi kèm giá gỗ để dao luôn, vừa tiện vừa đẹp, để trong bếp nhìn sang lắm!

# Xử lý phản đối

"Có cần mài không?" — 6 tháng mới cần mài 1 lần, mình tặng kèm thanh mài dao luôn rồi nha.

# Call to Action

Cả bộ 5 món + giá gỗ + thanh mài chỉ 459k. Comment "DAO" mình gửi link. Nhanh nha, hàng còn ít!

# Kết thúc

Ok vậy thôi nha! Mai mình live xoong chảo chống dính. Follow để đón xem!""",
    },
    {
        "category": "gia dụng",
        "persona_style": "thân thiện",
        "title": "Bình giữ nhiệt thông minh - 5 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Chào cả nhà, mình là Linh nè! Hôm nay mình muốn giới thiệu một sản phẩm nhỏ nhưng cực kỳ hữu ích. Ai hay mang nước đi làm, đi học thì chú ý nha!

# Giới thiệu sản phẩm

Đây là bình giữ nhiệt inox 304, dung tích 500ml. Điểm đặc biệt là nắp bình có màn hình LED hiển thị nhiệt độ nước bên trong!

Mình test luôn nha: đổ nước sôi 100 độ vào sáng nay, giờ 6 tiếng rồi, mọi người nhìn — vẫn 72 độ! Giữ nhiệt lạnh cũng tốt, bỏ đá vào giữ lạnh 12 tiếng.

Thiết kế nhỏ gọn, bỏ vừa balo, túi xách. Có 5 màu: đen, trắng, hồng, xanh navy, xanh mint.

# Xử lý phản đối

"Pin LED có hết không?" — Pin nút CR2032, dùng được khoảng 1 năm, thay rất dễ. "Rửa máy được không?" — Thân bình rửa tay nha, không ngâm nước phần nắp LED.

# Call to Action

Giá chỉ 199k, mua 2 giảm 30k. Comment "BINH + MAU" mình gửi link nha. Free ship!

# Kết thúc

Cảm ơn mọi người! Hẹn gặp lại live sau nha, love!""",
    },

    # --- TPCN / SỨC KHỎE (4 samples) ---
    {
        "category": "thực phẩm chức năng",
        "persona_style": "chuyên nghiệp",
        "title": "Collagen dạng nước - 10 phút",
        "quality_score": 5,
        "content": """# Mở đầu

Xin chào các chị em, mình là Phương — chuyên tư vấn sản phẩm sức khỏe và làm đẹp. Cảm ơn các bạn đã tham gia live hôm nay. Nhấn theo dõi để nhận thông tin sản phẩm mới mỗi tuần nhé.

# Giới thiệu sản phẩm

Hôm nay mình giới thiệu nước uống collagen dạng chai, mỗi hộp gồm 10 chai x 50ml.

Sản phẩm chứa 10.000mg Collagen peptide thủy phân — đây là dạng collagen có phân tử nhỏ, cơ thể hấp thu được đến 95%. Kết hợp với Vitamin C, E, và chiết xuất hạt nho để tăng hiệu quả chống lão hóa.

Sau 4 tuần sử dụng, các nghiên cứu cho thấy: da tăng độ đàn hồi 15%, giảm nếp nhăn rõ rệt, và móng tóc chắc khỏe hơn.

Mình đã uống 3 tháng, kết quả thực tế: da mình mịn màng hơn hẳn, đặc biệt vùng quanh mắt, nếp nhăn mờ đi nhiều. Tóc ít gãy rụng hơn.

Vị uống là vị việt quất, uống rất dễ chịu, không tanh. Mỗi ngày 1 chai sau bữa sáng hoặc trước khi ngủ.

# Xử lý phản đối

"Uống collagen có tăng cân không?" — Mỗi chai chỉ 15 calo, hoàn toàn không gây tăng cân.

"Bao lâu thấy hiệu quả?" — Thông thường 2-4 tuần sẽ thấy da mịn hơn. Để kết quả tốt nhất nên uống liên tục 3 tháng.

"Bầu/cho con bú uống được không?" — Sản phẩm an toàn, nhưng mình khuyên các chị nên hỏi ý kiến bác sĩ trước khi sử dụng.

# Call to Action

Giá 1 hộp 10 chai: 450.000đ. Mua liệu trình 3 hộp giảm còn 1.150.000đ — tiết kiệm 200k. Comment "COLLAGEN + SỐ HỘP" để đặt hàng. Miễn phí vận chuyển đơn từ 2 hộp.

# Kết thúc

Cảm ơn các bạn đã theo dõi. Thứ Tư tuần sau mình sẽ live về vitamin tổng hợp cho phụ nữ. Chúc các bạn sức khỏe!""",
    },
    {
        "category": "thực phẩm chức năng",
        "persona_style": "thân thiện",
        "title": "Trà giảm cân herbal - 5 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Chào mọi người nha! Mình là Vy, cảm ơn cả nhà đã vào live. Ai đang muốn giữ dáng healthy thì ở lại xem nha. Like cho mình nhiều nhiều!

# Giới thiệu sản phẩm

Đây là trà thảo mộc hỗ trợ giảm cân, thành phần 100% từ thiên nhiên: trà xanh, lá sen, cam thảo, và gừng.

Không phải thuốc giảm cân nha mọi người, đây là trà hỗ trợ trao đổi chất và giảm cảm giác thèm ăn. Uống kết hợp với ăn uống lành mạnh và vận động sẽ thấy hiệu quả.

Mình uống 1 tháng, giảm được 2kg mà không cần ăn kiêng khắc nghiệt. Chỉ cần bớt đồ ngọt và đi bộ 30 phút mỗi ngày.

Mỗi hộp 30 gói, mỗi ngày 1 gói pha với 200ml nước ấm. Uống sau bữa ăn 30 phút. Vị trà thơm, hơi ngọt nhẹ tự nhiên.

# Xử lý phản đối

"Có tác dụng phụ không?" — Thành phần tự nhiên nên rất an toàn. Một số bạn mới uống có thể đi ngoài nhẹ 1-2 ngày đầu, sau đó bình thường.

# Call to Action

Giá 1 hộp 159k, combo 3 hộp 399k. Comment "TRA" mình gửi link. Free ship!

# Kết thúc

Cảm ơn cả nhà! Chúc mọi người luôn khỏe đẹp. Hẹn live sau!""",
    },
    {
        "category": "thực phẩm chức năng",
        "persona_style": "vui vẻ",
        "title": "Vitamin gummy cho người lớn - 5 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Hello mọi người! Ai mà lười uống thuốc như mình thì vào đây! Hôm nay mình có sản phẩm hay lắm — vitamin mà ăn như kẹo dẻo! Thả tim cho mình đi nào!

# Giới thiệu sản phẩm

Vitamin gummy nè mọi người — viên kẹo dẻo chứa vitamin tổng hợp. Mỗi viên có vitamin A, C, D3, E, B6, B12, kẽm, và biotin.

Vị nho và cam, ăn ngon lắm luôn! Mỗi ngày 2 viên sau bữa ăn. Mình hay quên uống vitamin viên, nhưng cái này thì nhớ hoài vì ngon quá!

Mỗi lọ 60 viên, dùng được 1 tháng. Phù hợp cho người từ 12 tuổi trở lên.

# Xử lý phản đối

"Ăn như kẹo vậy có đủ liều không?" — Đủ nha, mỗi viên đã tính liều chuẩn rồi. "Có đường nhiều không?" — Mỗi viên chỉ 3g đường, ít hơn cả viên kẹo thường.

# Call to Action

Giá 1 lọ 249k. Mua 2 lọ tặng 1 hộp vitamin C effervescent. Comment "GUMMY" mình inbox link!

# Kết thúc

Vậy thôi nha, dễ thương quá đúng không! Hẹn mọi người live sau. Bye!""",
    },
    {
        "category": "thực phẩm chức năng",
        "persona_style": "chuyên nghiệp",
        "title": "Omega 3 dầu cá - 10 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Xin chào các bạn, mình là bác sĩ Minh — hiện đang tư vấn dinh dưỡng. Cảm ơn các bạn đã tham gia buổi live hôm nay. Mình sẽ chia sẻ về một sản phẩm bổ sung mà nhiều người cần nhưng ít người biết cách chọn đúng.

# Giới thiệu sản phẩm

Omega-3 dầu cá tinh khiết, hàm lượng EPA 360mg + DHA 240mg mỗi viên. Đây là tỉ lệ vàng được WHO khuyến nghị.

Tại sao cần bổ sung Omega-3? Vì chế độ ăn của người Việt Nam thường thiếu hụt nghiêm trọng loại axit béo này. Omega-3 hỗ trợ sức khỏe tim mạch, não bộ, mắt, và giảm viêm.

Sản phẩm này dùng dầu cá từ cá hồi Alaska, được tinh lọc phân tử để loại bỏ kim loại nặng và tạp chất. Mỗi lọ 90 viên, uống 2 viên/ngày sau bữa ăn.

Điểm khác biệt so với các sản phẩm rẻ tiền: hàm lượng EPA + DHA thực tế được ghi rõ trên nhãn. Nhiều sản phẩm chỉ ghi "1000mg dầu cá" nhưng hàm lượng Omega-3 thực tế rất thấp.

# Xử lý phản đối

"Uống dầu cá có bị tanh không?" — Viên nang enterik-coated, tan ở ruột nên không gây ợ tanh. "Ai nên uống?" — Người từ 18 tuổi trở lên, đặc biệt người ít ăn cá, người làm việc trí óc nhiều, người có cholesterol cao.

# Call to Action

Giá 1 lọ 90 viên: 389.000đ. Liệu trình 3 lọ: 999.000đ — tiết kiệm gần 170k. Comment "OMEGA" để đặt hàng. Ship COD toàn quốc.

# Kết thúc

Cảm ơn các bạn đã theo dõi. Sức khỏe là vốn quý nhất. Hẹn gặp lại trong buổi live tiếp theo về vitamin D3. Chào tạm biệt!""",
    },

    # --- ME VA BE (4 samples) ---
    {
        "category": "mẹ và bé",
        "persona_style": "thân thiện",
        "title": "Sữa bột cho bé 1-3 tuổi - 10 phút",
        "quality_score": 5,
        "content": """# Mở đầu

Chào các mẹ bỉm sữa nha! Mình là Thanh, mẹ của bé Bông 2 tuổi. Hôm nay mình muốn chia sẻ về sữa bột mà bé nhà mình đang dùng. Các mẹ nhớ follow để đón xem những review sản phẩm mẹ bé tiếp theo nhé!

# Giới thiệu sản phẩm

Đây là sữa bột dành cho bé 1-3 tuổi, công thức gần sữa mẹ. Bé Bông nhà mình chuyển sang uống sữa này từ lúc 1 tuổi và phát triển rất tốt.

Thành phần nổi bật: DHA và ARA cho phát triển não bộ, FOS/GOS prebiotic cho hệ tiêu hóa, canxi và vitamin D3 cho xương và răng.

Điều mình thích nhất là bé nhà mình trước đó hay bị táo bón khi đổi sữa, nhưng với sữa này thì không. Hệ tiêu hóa của bé rất ổn, đi ngoài đều đặn.

Hòa tan nhanh, không vón cục, vị sữa tự nhiên — bé Bông uống ngon lành. Mình pha theo hướng dẫn: 5 muỗng + 180ml nước ấm 40 độ.

Hộp 900g, dùng được khoảng 2-3 tuần tùy số cữ mỗi ngày.

# Xử lý phản đối

"Sữa này có đường không?" — Không thêm đường sucrose nha các mẹ, chỉ có lactose tự nhiên từ sữa. "Bé bị dị ứng đạm bò uống được không?" — Sản phẩm có đạm bò, nếu bé dị ứng thì không nên dùng, các mẹ nên hỏi bác sĩ.

# Call to Action

Giá 1 hộp 900g: 520.000đ. Mua 3 hộp giảm còn 1.450.000đ kèm 1 bình sữa chống sặc. Comment "SUA + TUOI BE" mình tư vấn thêm nha!

# Kết thúc

Cảm ơn các mẹ đã xem live! Chủ nhật tuần này mình live review bỉm cho bé nha. Chúc các mẹ và bé luôn khỏe mạnh!""",
    },
    {
        "category": "mẹ và bé",
        "persona_style": "vui vẻ",
        "title": "Đồ chơi xếp hình gỗ - 5 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Hello các mẹ ơi! Ai có bé 2-5 tuổi thì vào xem nha! Hôm nay mình có đồ chơi siêu cute và bổ ích cho bé. Like mạnh tay đi!

# Giới thiệu sản phẩm

Bộ xếp hình gỗ Montessori nè — 60 miếng gỗ, nhiều hình dạng và màu sắc. Gỗ sơn nước an toàn, bé cắn cũng không sao!

Bé chơi xếp hình giúp phát triển trí tuệ, tư duy logic, và khả năng nhận biết màu sắc, hình khối. Bé Sóc nhà mình 3 tuổi chơi mê luôn, ngồi chơi 30 phút không cần mẹ!

Gỗ dày 1.5cm, bo tròn cạnh, không sắc nhọn. Sơn nước an toàn theo tiêu chuẩn châu Âu EN71.

Hộp đựng có nắp, tiện dọn dẹp. Mình hay cho bé chơi xong tự bỏ vào hộp — vừa chơi vừa tập tính tự lập!

# Xử lý phản đối

"3 tuổi chơi có sớm không?" — Không sớm nha, bé từ 18 tháng đã có thể chơi các khối đơn giản rồi. "Gỗ có mùi không?" — Không mùi, gỗ tự nhiên rất an toàn.

# Call to Action

Bộ 60 miếng chỉ 259k. Mua kèm bảng vẽ gỗ thêm 99k. Comment "XEPHINH" mình inbox link!

# Kết thúc

Yêu các mẹ! Hẹn live sau nha, mình sẽ review sách vải cho bé. Bye bye!""",
    },
    {
        "category": "mẹ và bé",
        "persona_style": "thân thiện",
        "title": "Địu em bé ergonomic - 10 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Chào các mẹ nha! Mình là Hồng, mẹ bỉm 2 con. Hôm nay mình review sản phẩm mà mình ước gì biết sớm hơn từ lúc sinh bé đầu. Follow mình để xem thêm review mẹ bé nha!

# Giới thiệu sản phẩm

Đây là địu em bé ergonomic, hỗ trợ tư thế ngồi chữ M cho bé — đây là tư thế mà bác sĩ nhi khoa khuyến nghị, tốt cho hông và cột sống bé.

Địu có 4 tư thế: địu trước mặt vào trong (0-4 tháng), mặt ra ngoài (4-6 tháng), địu hông (6-12 tháng), và địu sau lưng (12 tháng+). Dùng từ sơ sinh đến 3 tuổi (tối đa 20kg).

Đệm vai rộng và lưng có đai hỗ trợ, mình địu bé 10kg đi chợ 1 tiếng mà vai không đau. Trước mình dùng địu rẻ tiền, đi 20 phút là mỏi lưng.

Chất vải thông thoáng, có lưới thoát khí ở phần bé ngồi. Mùa hè dùng vẫn mát.

Có 4 màu: xám, đen, navy, và hồng pastel.

# Xử lý phản đối

"Giá hơi cao?" — So với đau lưng và tư thế xấu cho bé thì đáng đầu tư lắm các mẹ ơi. Mình dùng từ bé đầu đến bé thứ 2 vẫn còn tốt. "Bé sơ sinh dùng được không?" — Được, có insert đệm sơ sinh đi kèm.

# Call to Action

Giá 690k. Mua kèm yếm chống nhớt thêm 49k. Comment "DIU + MAU" mình gửi link. Free ship!

# Kết thúc

Cảm ơn các mẹ! Thứ 6 tuần này mình live review xe đẩy cho bé nha. Hẹn gặp lại!""",
    },
    {
        "category": "mẹ và bé",
        "persona_style": "chuyên nghiệp",
        "title": "Ghế ăn dặm cho bé - 10 phút",
        "quality_score": 4,
        "content": """# Mở đầu

Xin chào các bố mẹ, mình là Tú — chuyên review đồ dùng cho bé. Cảm ơn các bạn đã tham gia live. Hôm nay mình giới thiệu ghế ăn dặm mà mình đánh giá rất cao sau 6 tháng sử dụng.

# Giới thiệu sản phẩm

Ghế ăn dặm đa năng này có 5 chế độ điều chỉnh: ghế ăn cao, ghế ăn thấp, ghế nằm, ghế rung, và booster seat. Sử dụng từ 6 tháng đến 6 tuổi.

Khung ghế bằng thép không gỉ, chịu lực tốt. Đệm ngồi PU dễ lau chùi — bé ăn dơ mấy cũng lau sạch trong 10 giây.

Khay ăn có 2 lớp: lớp trong tháo rửa, lớp ngoài cố định. Thiết kế này rất tiện — xong bữa chỉ tháo lớp trong ra rửa, không cần tháo toàn bộ.

Chân ghế có bánh xe khóa, di chuyển dễ dàng trong nhà mà vẫn an toàn khi bé ngồi.

Đai an toàn 5 điểm, bé không tự leo ra được. Mình rất yên tâm khi cho bé ngồi ăn.

# Xử lý phản đối

"Ghế có gấp gọn được không?" — Gấp phẳng 15cm, đứng sau cánh cửa được. "Bé 6 tháng ngồi có vững không?" — Ghế điều chỉnh được độ ngả lưng, bé mới tập ngồi vẫn an toàn.

# Call to Action

Giá 1.490.000đ kèm full phụ kiện. Comment "GHE" để nhận tư vấn và link đặt hàng. Bảo hành khung ghế 3 năm.

# Kết thúc

Cảm ơn các bạn. Tuần sau mình sẽ live so sánh top 3 ghế ăn dặm bán chạy nhất. Nhấn theo dõi để không bỏ lỡ nhé!""",
    },
]


def seed_script_samples():
    """Insert script samples and generate embeddings."""
    sync_db_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = create_engine(sync_db_url)

    genai.configure(api_key=settings.gemini_api_key)

    with Session(engine) as session:
        # Check if already seeded
        count = session.execute(
            text("SELECT COUNT(*) FROM script_samples")
        ).scalar_one()
        if count >= 20:
            print(f"Already have {count} script samples, skipping seed.")
            return

        for i, sample in enumerate(SAMPLES, 1):
            print(f"  [{i}/{len(SAMPLES)}] Embedding: {sample['title']}...")

            # Generate embedding
            try:
                embed_text = f"{sample['title']}. {sample['category']}. {sample['persona_style']}. {sample['content'][:500]}"
                result = genai.embed_content(
                    model="models/text-embedding-004",
                    content=embed_text,
                    task_type="RETRIEVAL_DOCUMENT",
                )
                embedding = result["embedding"]
            except Exception as e:
                print(f"    WARNING: Embedding failed: {e}, inserting without embedding")
                embedding = None

            session.execute(
                text("""
                    INSERT INTO script_samples (
                        category, persona_style, title, content,
                        quality_score, embedding, created_by, created_at
                    ) VALUES (
                        :category, :persona_style, :title, :content,
                        :quality_score, :embedding, 'seed', :now
                    )
                """),
                {
                    "category": sample["category"],
                    "persona_style": sample["persona_style"],
                    "title": sample["title"],
                    "content": sample["content"],
                    "quality_score": sample["quality_score"],
                    "embedding": str(embedding) if embedding else None,
                    "now": datetime.now(timezone.utc),
                },
            )

        session.commit()
        print(f"Seeded {len(SAMPLES)} script samples successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_script_samples()
