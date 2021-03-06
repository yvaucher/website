# -*- coding: utf-8 -*-
# include bug fix from rgo-odoo https://github.com/odoo/odoo/pull/3097
# + remove specified order when calling blog_post.search

from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website_blog.controllers.main import WebsiteBlog
from openerp.addons.website_blog.controllers.main import QueryURL
from openerp.addons.website.models.website import slug
from openerp import SUPERUSER_ID


class WebsiteBlog(WebsiteBlog):
    _blog_post_per_page = 20
    _post_comment_per_page = 10

    @http.route([
        '/blog/<model("blog.blog"):blog>',
        '/blog/<model("blog.blog"):blog>/page/<int:page>',
        '/blog/<model("blog.blog"):blog>/tag/<model("blog.tag"):tag>',
        '/blog/<model("blog.blog"):blog>/tag/<model("blog.tag")' +
        ':tag>/page/<int:page>',
    ], type='http', auth="public", website=True)
    def blog(self, blog=None, tag=None, page=1, **opt):
        """ Prepare all values to display the blog.

        :return dict values: values for the templates, containing

         - 'blog': current blog
         - 'blogs': all blogs for navigation
         - 'pager': pager of posts
         - 'tag': current tag
         - 'tags': all tags, for navigation
         - 'nav_list': a dict [year][month] for archives navigation
         - 'date': date_begin optional parameter, used in archives navigation
         - 'blog_url': help object to create URLs
        """
        date_begin, date_end = opt.get('date_begin'), opt.get('date_end')

        cr, uid, context = request.cr, request.uid, request.context
        blog_post_obj = request.registry['blog.post']

        blog_obj = request.registry['blog.blog']
        blog_ids = blog_obj.search(
            cr, uid, [], order="create_date asc", context=context)
        blogs = blog_obj.browse(cr, uid, blog_ids, context=context)

        domain = []
        if blog:
            domain += [('blog_id', '=', blog.id)]
        if tag:
            domain += [('tag_ids', 'in', tag.id)]
        if date_begin and date_end:
            domain += [("website_publication_date", ">=", date_begin),
                       ("website_publication_date", "<=", date_end)]

        blog_url = QueryURL(
            '', ['blog', 'tag'], blog=blog, tag=tag,
            date_begin=date_begin, date_end=date_end)
        post_url = QueryURL(
            '', ['blogpost'], tag_id=tag and tag.id or None,
            date_begin=date_begin, date_end=date_end)

        blog_post_ids = blog_post_obj.search(
            cr, uid, domain, context=context)
        blog_posts = blog_post_obj.browse(
            cr, uid, blog_post_ids, context=context)

        pager = request.website.pager(
            url=blog_url(),
            total=len(blog_posts),
            page=page,
            step=self._blog_post_per_page,
        )
        pager_begin = (page - 1) * self._blog_post_per_page
        pager_end = page * self._blog_post_per_page
        blog_posts = blog_posts[pager_begin:pager_end]

        tags = blog.all_tags()[blog.id]

        values = {
            'blog': blog,
            'blogs': blogs,
            'tags': tags,
            'tag': tag,
            'blog_posts': blog_posts,
            'pager': pager,
            'nav_list': self.nav_list(),
            'blog_url': blog_url,
            'post_url': post_url,
            'date': date_begin,
        }
        response = request.website.render(
            "website_blog.blog_post_short", values)
        return response

    @http.route([
        '''/blog/<model("blog.blog"):blog>/post/<model("blog.post",''' +
        ''' "[('blog_id','=',blog[0])]"):blog_post>''',
    ], type='http', auth="public", website=True)
    def blog_post(self, blog, blog_post, tag_id=None, page=1,
                  enable_editor=None, **post):
        """ Prepare all values to display the blog.

        :return dict values: values for the templates, containing

         - 'blog_post': browse of the current post
         - 'blog': browse of the current blog
         - 'blogs': list of browse records of blogs
         - 'tag': current tag, if tag_id in parameters
         - 'tags': all tags, for tag-based navigation
         - 'pager': a pager on the comments
         - 'nav_list': a dict [year][month] for archives navigation
         - 'next_post': next blog post, to direct the user towards the next
                       post
        """
        cr, uid, context = request.cr, request.uid, request.context
        tag_obj = request.registry['blog.tag']
        blog_post_obj = request.registry['blog.post']
        date_begin, date_end = post.get('date_begin'), post.get('date_end')

        pager_url = "/blogpost/%s" % blog_post.id

        pager = request.website.pager(
            url=pager_url,
            total=len(blog_post.website_message_ids),
            page=page,
            step=self._post_comment_per_page,
            scope=7
        )
        pager_begin = (page - 1) * self._post_comment_per_page
        pager_end = page * self._post_comment_per_page
        comments = blog_post.website_message_ids[pager_begin:pager_end]

        def get_next_post_id(blog_post_ids, current_blog_post_id):
            if not blog_post_ids or not current_blog_post_id:
                return False
            cur_blog_idx = blog_post_ids.index(current_blog_post_id)
            return blog_post_ids[0 if cur_blog_idx == len(blog_post_ids) - 1
                                 else cur_blog_idx + 1]

        def check_blog_post_status(blog_post_id, visited_ids):
            # recursive check to see if the blog posts which client earlier
            # visited(stored in 'visited_blogs' cookies) are been 'unpublished'
            #  or deleted.
            if not blog_post_id:
                return False
            if blog_post_obj.search(
                    cr, uid, [('id', '=', blog_post_id)], context=context):
                return blog_post_id
            next_blog_post_id = get_next_post_id(visited_ids, blog_post_id)
            visited_ids.remove(blog_post_id)
            return check_blog_post_status(next_blog_post_id, visited_ids)

        tag = None
        if tag_id:
            tag = request.registry['blog.tag'].browse(
                request.cr, request.uid, int(tag_id), context=request.context)
        post_url = QueryURL(
            '', ['blogpost'], blogpost=blog_post, tag_id=tag_id,
            date_begin=date_begin, date_end=date_end)
        blog_url = QueryURL(
            '', ['blog', 'tag'], blog=blog_post.blog_id, tag=tag,
            date_begin=date_begin, date_end=date_end)

        if not blog_post.blog_id.id == blog.id:
            return request.redirect(
                "/blog/%s/post/%s" % (slug(blog_post.blog_id),
                                      slug(blog_post)))

        tags = tag_obj.browse(
            cr, uid, tag_obj.search(
                cr, uid, [], context=context), context=context)

        # Find next Post
        visited_blogs = request.httprequest.cookies.get('visited_blogs') or ''
        visited_ids = filter(None, visited_blogs.split(','))
        visited_ids = map(lambda x: int(x), visited_ids)
        if blog_post.id not in visited_ids:
            visited_ids.append(blog_post.id)
        next_post_id = blog_post_obj.search(cr, uid, [
            ('id', 'not in', visited_ids),
        ], order='website_publication_date desc', limit=1, context=context)
        if not next_post_id:
            next_post_id = get_next_post_id(visited_ids, blog_post.id)
            next_post_id = check_blog_post_status(next_post_id, visited_ids)
        next_post = next_post_id and blog_post_obj.browse(
            cr, uid, next_post_id, context=context) or False

        values = {
            'tags': tags,
            'tag': tag,
            'blog': blog,
            'blog_post': blog_post,
            'main_object': blog_post,
            'nav_list': self.nav_list(),
            'enable_editor': enable_editor,
            'next_post': next_post,
            'date': date_begin,
            'post_url': post_url,
            'blog_url': blog_url,
            'pager': pager,
            'comments': comments,
        }
        response = request.website.render(
            'website_blog.blog_post_complete', values)
        response.set_cookie('visited_blogs', ','.join(map(str, visited_ids)))

        request.session[request.session_id] = request.session.get(
            request.session_id, [])
        if not (blog_post.id in request.session[request.session_id]):
            request.session[request.session_id].append(blog_post.id)
            # Increase counter
            blog_post_obj.write(cr, SUPERUSER_ID, [blog_post.id], {
                'visits': blog_post.visits+1,
            }, context=context)
        return response
