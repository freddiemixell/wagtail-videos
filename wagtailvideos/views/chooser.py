from __future__ import absolute_import, print_function, unicode_literals

import json

from django.core.urlresolvers import reverse
from django.shortcuts import get_object_or_404, render
from wagtail.utils.pagination import paginate
from wagtail.wagtailadmin.forms import SearchForm
from wagtail.wagtailadmin.modal_workflow import render_modal_workflow
from wagtail.wagtailadmin.utils import PermissionPolicyChecker
from wagtail.wagtailcore.models import Collection
from wagtail.wagtailsearch import index as search_index
from wagtail.wagtailsearch.backends import get_search_backends

from wagtailvideos.forms import get_video_form
from wagtailvideos.models import Video
from wagtailvideos.permissions import permission_policy

permission_checker = PermissionPolicyChecker(permission_policy)


def get_video_json(video):
    """
    helper function: given an image, return the json to pass back to the
    image chooser panel
    """

    return json.dumps({
        'id': video.id,
        'edit_link': reverse('wagtailvideos:edit', args=(video.id,)),
        'title': video.title,
        'preview': {
            'url': video.thumbnail.url,
        }
    })


def chooser(request):
    VideoForm = get_video_form(Video)
    uploadform = VideoForm()

    videos = Video.objects.order_by('-created_at')

    q = None
    if (
        'q' in request.GET or 'p' in request.GET or 'tag' in request.GET or
        'collection_id' in request.GET
    ):
        # this request is triggered from search, pagination or 'popular tags';
        # we will just render the results.html fragment
        collection_id = request.GET.get('collection_id')
        if collection_id:
            videos = videos.filter(collection=collection_id)

        searchform = SearchForm(request.GET)
        if searchform.is_valid():
            q = searchform.cleaned_data['q']

            videos = videos.search(q)
            is_searching = True
        else:
            is_searching = False

            tag_name = request.GET.get('tag')
            if tag_name:
                videos = videos.filter(tags__name=tag_name)

        # Pagination
        paginator, videos = paginate(request, videos, per_page=12)

        return render(request, "wagtailvideos/chooser/results.html", {
            'videos': videos,
            'is_searching': is_searching,
            'query_string': q,
        })
    else:
        searchform = SearchForm()

        collections = Collection.objects.all()
        if len(collections) < 2:
            collections = None

        paginator, videos = paginate(request, videos, per_page=12)

    return render_modal_workflow(request, 'wagtailvideos/chooser/chooser.html', 'wagtailvideos/chooser/chooser.js', {
        'videos': videos,
        'uploadform': uploadform,
        'searchform': searchform,
        'is_searching': False,
        'query_string': q,
        'popular_tags': Video.popular_tags(),
        'collections': collections,
    })


def video_chosen(request, video_id):
    video = get_object_or_404(Video, id=video_id)

    return render_modal_workflow(
        request, None, 'wagtailvideos/chooser/video_chosen.js',
        {'video_json': get_video_json(video)}
    )


@permission_checker.require('add')
def chooser_upload(request):
    VideoForm = get_video_form(Video)

    searchform = SearchForm()

    if request.POST:
        video = Video(uploaded_by_user=request.user)
        form = VideoForm(request.POST, request.FILES, instance=video)

        if form.is_valid():
            video.uploaded_by_user = request.user
            video.save()

            # Reindex the video to make sure all tags are indexed
            from wagtail.wagtailcore import __version__
            if __version__.startswith("1.4"):
                for backend in get_search_backends():
                    backend.add(video)
            else:
                search_index.insert_or_update_object(video)

            return render_modal_workflow(
                request, None, 'wagtailvideos/chooser/video_chosen.js',
                {'video_json': get_video_json(video)}
            )
    else:
        form = VideoForm()

    videos = Video.objects.order_by('title')
    paginator, videos = paginate(request, videos, per_page=12)

    return render_modal_workflow(
        request, 'wagtailvideos/chooser/chooser.html', 'wagtailvideos/chooser/chooser.js',
        {'videos': videos, 'uploadform': form, 'searchform': searchform}
    )
