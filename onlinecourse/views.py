from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.views import generic
from django.contrib.auth import login, logout, authenticate
import logging

from .models import Course, Enrollment, Submission, Choice

logger = logging.getLogger(__name__)


def registration_request(request):
    context = {}
    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_registration_bootstrap.html',
            context
        )
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('psw')
        first_name = request.POST.get('firstname', '')
        last_name = request.POST.get('lastname', '')

        if not username or not password:
            context['message'] = 'Username and password are required.'
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )

        if User.objects.filter(username=username).exists():
            context['message'] = 'User already exists.'
            return render(
                request,
                'onlinecourse/user_registration_bootstrap.html',
                context
            )

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name
        )
        login(request, user)
        return redirect('onlinecourse:index')


def login_request(request):
    context = {}
    if request.method == 'GET':
        return render(
            request,
            'onlinecourse/user_login_bootstrap.html',
            context
        )
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('psw')
        user = authenticate(
            request,
            username=username,
            password=password
        )
        if user is not None:
            login(request, user)
            return redirect('onlinecourse:index')
        context['message'] = 'Invalid username or password.'
        return render(
            request,
            'onlinecourse/user_login_bootstrap.html',
            context
        )


def logout_request(request):
    logout(request)
    return redirect('onlinecourse:index')


def check_if_enrolled(user, course):
    return Enrollment.objects.filter(
        user=user,
        course=course
    ).exists()


class CourseListView(generic.ListView):
    template_name = 'onlinecourse/course_list_bootstrap.html'
    context_object_name = 'course_list'

    def get_queryset(self):
        return Course.objects.order_by('-pub_date')


class CourseDetailView(generic.DetailView):
    model = Course
    # The assignment requests this exact plural filename.
    template_name = 'onlinecourse/course_details_bootstrap.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        course = self.get_object()
        context['is_enrolled'] = False
        if self.request.user.is_authenticated:
            context['is_enrolled'] = check_if_enrolled(
                self.request.user,
                course
            )
        return context


def enroll(request, course_id):
    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)
    Enrollment.objects.get_or_create(
        user=request.user,
        course=course
    )
    return redirect(
        'onlinecourse:course_details',
        pk=course.id
    )


def extract_answers(request):
    selected_ids = []
    for key in request.POST:
        if key.startswith('answer_') or key.startswith('choice'):
            for value in request.POST.getlist(key):
                try:
                    selected_ids.append(int(value))
                except (TypeError, ValueError):
                    continue
    # Remove duplicate choice IDs.
    return list(set(selected_ids))


def submit(request, course_id):
    if request.method != 'POST':
        return redirect(
            'onlinecourse:course_details',
            pk=course_id
        )

    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)
    enrollment = get_object_or_404(
        Enrollment,
        user=request.user,
        course=course
    )

    submission = Submission.objects.create(
        enrollment=enrollment
    )

    selected_ids = extract_answers(request)
    valid_choices = Choice.objects.filter(
        id__in=selected_ids,
        question__course=course
    )
    submission.choices.set(valid_choices)

    return redirect(
        'onlinecourse:show_exam_result',
        course_id=course.id,
        submission_id=submission.id
    )


def show_exam_result(request, course_id, submission_id):
    if not request.user.is_authenticated:
        return redirect('onlinecourse:login')

    course = get_object_or_404(Course, pk=course_id)

    # A learner can only view their own submission for this course.
    submission = get_object_or_404(
        Submission,
        pk=submission_id,
        enrollment__course=course,
        enrollment__user=request.user
    )

    total_score = 0
    total_possible = 0
    question_results = []

    for question in course.question_set.all():
        selected_ids = list(
            submission.choices.filter(question=question)
            .values_list('id', flat=True)
        )
        is_correct = question.is_get_score(selected_ids)
        score = question.grade if is_correct else 0

        total_score += score
        total_possible += question.grade

        question_results.append({
            'question': question,
            'choices': question.choice_set.all(),
            'selected_ids': selected_ids,
            'score': score,
            'is_correct': is_correct,
        })

    percentage = (
        round((total_score / total_possible) * 100, 2)
        if total_possible > 0 else 0
    )

    context = {
        'course': course,
        'submission': submission,
        'question_results': question_results,
        'grade': total_score,
        'possible': total_possible,
        'total_score': total_score,
        'total_possible': total_possible,
        'percentage': percentage,
    }

    return render(
        request,
        'onlinecourse/exam_result_bootstrap.html',
        context
    )
