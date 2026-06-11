import pkg_resources
import json
from xblock.core import XBlock
from xblock.fields import Scope, String, Dict, Float, Boolean, List
from xblock.fragment import Fragment


class SingleQuizXBlock(XBlock):
    """
    XBlock trắc nghiệm 1 đáp án kèm ảnh (carousel) và video YouTube.

    Logic chấm điểm giống multiplechoiceresponse của edx-platform:
    - Learner chỉ được chọn 1 đáp án
    - So sánh với choice có correct=true
    - Trả kết quả correct/incorrect

    Dữ liệu:
      - display_name: tên hiển thị
      - question_html: nội dung câu hỏi (rich HTML)
      - choices: danh sách đáp án [{id, html, correct}]
      - images: mảng URL ảnh (1 ảnh = hiển thị đơn, >=2 = carousel)
      - video_url: YouTube URL (hoặc rỗng)
      - explanation_html: giải thích đáp án (hiện khi đúng)
      - hints: mảng gợi ý text

    Completion: active (chấm điểm khi submit) — FE gọi submit_answers
    """

    display_name = String(
        display_name="Display Name",
        help="Tên hiển thị cho học viên.",
        default="Trắc nghiệm 1 đáp án",
        scope=Scope.settings,
    )

    question_html = String(
        display_name="Question HTML",
        help="Nội dung câu hỏi (rich HTML).",
        default="<p>Nhập câu hỏi của bạn vào đây</p>",
        scope=Scope.settings,
    )

    choices = List(
        display_name="Choices",
        help="Danh sách đáp án. Mỗi item: {id, html, correct}.",
        default=[
            {"id": "c1", "html": "Đáp án đúng", "correct": True},
            {"id": "c2", "html": "Đáp án sai", "correct": False},
        ],
        scope=Scope.settings,
    )

    images = List(
        display_name="Images",
        help="Mảng URL ảnh. 1 ảnh = hiển thị đơn, >=2 ảnh = carousel.",
        default=[],
        scope=Scope.settings,
    )

    video_url = String(
        display_name="Video URL",
        help="YouTube URL (hoặc để trống nếu không có video).",
        default="",
        scope=Scope.settings,
    )

    explanation_html = String(
        display_name="Explanation HTML",
        help="Giải thích đáp án (hiện khi trả lời đúng).",
        default="",
        scope=Scope.settings,
    )

    hints = List(
        display_name="Hints",
        help="Mảng gợi ý text.",
        default=[],
        scope=Scope.settings,
    )

    # ── User state ──
    score = Float(
        default=0.0,
        scope=Scope.user_state,
    )

    completed = Boolean(
        default=False,
        scope=Scope.user_state,
    )

    has_score = True
    icon_class = 'problem'

    def resource_string(self, path):
        """Đọc file tài nguyên (HTML/JS/CSS)."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def student_view(self, context=None):
        """
        Dành cho LMS hoặc Studio Preview.
        Quiz này được render hoàn toàn bằng FE 5173.
        """
        html = """
        <div style="padding: 20px; text-align: center; background: #f0f0f0; border-radius: 8px;">
            <h3>{display_name}</h3>
            <p><i>⚠️ Quiz này được thiết kế để hiển thị trên App React Frontend.</i></p>
            <p>Vui lòng xem trước trên hệ thống Frontend 5173.</p>
        </div>
        """.format(
            display_name=self.display_name,
        )
        return Fragment(html)

    def studio_view(self, context=None):
        """
        Giao diện CMS dành cho mentor.
        Frontend-shell sẽ gọi studio_submit trực tiếp, studio_view chỉ là fallback.
        """
        html = self.resource_string("static/html/studio_view.html")
        data_json = json.dumps({
            "choices": self.choices,
            "images": self.images,
            "hints": self.hints,
        }).replace("'", "&#39;")
        frag = Fragment(html.format(
            display_name=self.display_name,
            question_html=self.question_html or "",
            video_url=self.video_url or "",
            explanation_html=self.explanation_html or "",
            data_json=data_json,
        ))
        frag.add_javascript(self.resource_string("static/js/studio_view.js"))
        frag.initialize_js('SingleQuizStudioView')
        return frag

    @XBlock.json_handler
    def studio_submit(self, data, suffix=''):
        """
        Tiếp nhận Data từ frontend-shell và lưu vào MongoDB.
        """
        display_name = data.get('display_name')
        if display_name is not None:
            self.display_name = display_name

        question_html = data.get('question_html')
        if question_html is not None:
            self.question_html = question_html

        choices_raw = data.get('choices')
        if choices_raw is not None:
            if isinstance(choices_raw, str):
                try:
                    self.choices = json.loads(choices_raw)
                except ValueError:
                    return {"result": "error", "message": "Sai định dạng JSON cho choices."}
            else:
                self.choices = choices_raw

        images_raw = data.get('images')
        if images_raw is not None:
            if isinstance(images_raw, str):
                try:
                    self.images = json.loads(images_raw)
                except ValueError:
                    return {"result": "error", "message": "Sai định dạng JSON cho images."}
            else:
                self.images = images_raw

        video_url = data.get('video_url')
        if video_url is not None:
            self.video_url = video_url.strip()

        explanation_html = data.get('explanation_html')
        if explanation_html is not None:
            self.explanation_html = explanation_html

        hints_raw = data.get('hints')
        if hints_raw is not None:
            if isinstance(hints_raw, str):
                try:
                    self.hints = json.loads(hints_raw)
                except ValueError:
                    return {"result": "error", "message": "Sai định dạng JSON cho hints."}
            else:
                self.hints = hints_raw

        return {"result": "success"}

    def student_view_data(self, context=None):
        """
        Output cho API /api/courses/v1/blocks/ (Sử dụng bởi FE React).
        BẮT BUỘC KHÔNG ĐƯỢC CHỨA ĐÁNG ÁN ĐÚNG (correct field).
        """
        safe_choices = []
        for choice in self.choices:
            safe_choice = {
                "id": choice.get("id"),
                "html": choice.get("html", ""),
            }
            safe_choices.append(safe_choice)

        return {
            "display_name": self.display_name,
            "question_html": self.question_html or "",
            "choices": safe_choices,
            "images": list(self.images) if self.images else [],
            "video_url": self.video_url or "",
            "explanation_html": self.explanation_html or "",
            "hints": list(self.hints) if self.hints else [],
            "completed": self.completed,
            "score": self.score,
        }

    @XBlock.json_handler
    def submit_answers(self, data, suffix=''):
        """
        Chấm điểm đáp án. React gửi payload: {"answer": "c1"}
        Logic: Single choice — chỉ 1 đáp án đúng.
        """
        student_answer = data.get("answer", "")
        if not student_answer:
            return {"status": "error", "message": "Chưa chọn đáp án."}

        # Tìm đáp án đúng trong danh sách choices
        correct_id = None
        for choice in self.choices:
            if choice.get("correct") is True:
                correct_id = choice.get("id")
                break

        if correct_id is None:
            return {"status": "error", "message": "Câu hỏi chưa được cấu hình đáp án đúng."}

        is_correct = (str(student_answer) == str(correct_id))

        if is_correct:
            if not self.completed:
                self.completed = True
                self.score = 1.0
                self.runtime.publish(self, 'grade', {'value': 1.0, 'max_value': 1.0})
            return {"status": "correct", "message": "Chính xác! Bạn đã trả lời đúng."}
        else:
            return {"status": "incorrect", "message": "Chưa đúng, hãy thử lại."}
