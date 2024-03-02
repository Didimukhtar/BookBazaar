from django.shortcuts import render

from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import UserSerializer,RegisterSerializer, UserProfileSerializer, UserSerializer, BookSerializer, FollowSerializer, ReviewSerializer
from django.contrib.auth.models import User
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated 
from rest_framework import generics, status
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from .models import UserProfile, Book, Follow, Review, Comment, Like, Cart, CartItem, Order, OrderItem
from .permissions import IsUserProfileOwnerOrReadOnly, IsOwnerOrReadOnly, IsCommentOwnerOrBookOwner
from rest_framework import viewsets, permissions
from .serializers import CommentSerializer, LikeSerializer, CartSerializer, CartItemSerializer, OrderSerializer, OrderItemSerializer
from rest_framework import status
from django.core.paginator import Paginator
from api.notification.signals import user_registered, user_followed, book_liked, book_commented





class UserList(generics.ListAPIView):
    """
    Retrieve a list of all users.
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer


class UserDetail(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a user instance.
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer

   
# Class based view to Get User Details using Token Authentication
class UserProfileDetail(generics.RetrieveAPIView):
    """
    Retrieve the user profile of the currently logged-in user.
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        # Retrieve the profile associated with the currently authenticated user
        return self.request.user.profile

class UserProfileEdit(generics.RetrieveUpdateDestroyAPIView):
    """
    Update the user profile of the currently logged-in user.
    """
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, IsUserProfileOwnerOrReadOnly]

    def get_object(self):
        # Retrieve the profile associated with the currently authenticated user
        return self.request.user.profile
    
    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": "Profile has been deleted."}, status=status.HTTP_204_NO_CONTENT)
    

   


# Class based view to register user
class RegisterUserAPIView(generics.CreateAPIView):
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer
    @swagger_auto_schema(operation_description="Register a new user")
    
    def post(self, request, *args, **kwargs):
        user_registered.send(sender=user_registered, user=request.user)
        return super().post(request, *args, **kwargs)

# Logout view
class LogoutView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(operation_description="Logout and invalidate the user's token")
    def post(self, request):
        """
        Logout and invalidate the user's token.
        """
        request.user.auth_token.delete()
        return Response({"message": "Successfully logged out."})


# ViewSets define the view behavior.
class BookViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows books to be viewed or edited.
    """
    serializer_class = BookSerializer
    permission_classes = [permissions.IsAuthenticated]  # Only authenticated users can access

    def get_queryset(self):
        # Filter queryset to only include books owned by the current user
        return Book.objects.filter(owner=self.request.user.profile)

    def perform_create(self, serializer):
        # Set the owner of the book to the current user
        serializer.save(owner=self.request.user.profile)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": f"Book '{instance.title}' has been deleted."}, status=status.HTTP_204_NO_CONTENT)

    def perform_destroy(self, instance):
        instance.delete()



class AllBooksViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows all books to be viewed.
    """
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [AllowAny]  # Allow anyone to view all book

class BookInteractionViewSet(viewsets.ViewSet):
    """
    API endpoint that allows interactions with books (e.g., liking, commenting, reviewing).
    """
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]


    def create_like(self, request, book_id):
    
        try:
            book = Book.objects.get(id=book_id)
            like, created = Like.objects.get_or_create(user=request.user, book=book)
            if created:
                book_liked.send(sender=book_liked, liker=request.user, book=book)
                return Response({'message': 'Book liked successfully.'}, status=status.HTTP_201_CREATED)
            else:
                return Response({'message': 'You have already liked this book.'}, status=status.HTTP_400_BAD_REQUEST)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found.'}, status=status.HTTP_404_NOT_FOUND)

    def follow_author(self, request, author_id):
        try:
            
            author = UserProfile.objects.get(id=author_id)
            # Check if the user is trying to follow themselves
            if request.user == author.user:
                return Response({'error': 'You cannot follow yourself.'}, status=status.HTTP_400_BAD_REQUEST)
        
            
            follow, created = Follow.objects.get_or_create(user=request.user, followed_user=author.user)
            print(request.user, author.user)
            if created:
                user_followed.send(sender=user_followed, follower=request.user, followed_user=author.user)
                return Response({'message': 'Author followed successfully.'}, status=status.HTTP_201_CREATED)
            else:
                return Response({'message': f"You are already following this author. {follow.followed_user}"}, status=status.HTTP_400_BAD_REQUEST)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Author not found.'}, status=status.HTTP_404_NOT_FOUND)

   
    def create_comment(self, request):
        serializer = CommentSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(commenter=request.user)
            book_commented.send(sender=None, commenter=request.user, book=serializer.validated_data['book_id'])
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    def create_review(self, request):
        serializer = ReviewSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(reviewer=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def update_review(self, request, book_id, review_id):
        try:
            review = Review.objects.get(id=review_id, book_id=book_id, reviewer=request.user)
            serializer = ReviewSerializer(review, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    def retrieve_review(self, request, book_id, review_id):
        try:
            review = Review.objects.get(id=review_id, book_id=book_id)
            serializer = ReviewSerializer(review, context={'request': request})
            return Response(serializer.data)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    def delete_review(self, request, book_id, review_id):
        try:
            review = Review.objects.get(id=review_id, book_id=book_id, reviewer=request.user)
            review.delete()
            return Response({"Message": f"Review with the id: {review_id} has been deleted"}, status=status.HTTP_204_NO_CONTENT)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)

    def list_followers(self, request, author_id):
        author = UserProfile.objects.get(id=author_id)
        followers = Follow.objects.filter(followed_user_id=author.user.id)
        paginator = Paginator(followers, 10)  # Adjust the page size as needed
        page_number = request.query_params.get('page', 1)
        page = paginator.get_page(page_number)

        # Check if there's a next page
        if page.has_next():
            next_page_number = page.next_page_number()
        else:
            next_page_number = None

        serializer = FollowSerializer(page, many=True, context={'request': request})

        if not serializer.data:
            return Response({'message': 'No followers found.'}, status=status.HTTP_404_NOT_FOUND)

        # Optionally, you can include the next page number in the response
        response_data = {
            'followers': serializer.data,
            'next_page_number': next_page_number
        }

        return Response(response_data)
    

    def delete_follow(self, request, author_id):
        try:
            
            follow = Follow.objects.get(user=request.user)
            print(follow.user)
            follow.delete()
            return Response({"Message": f"You have sucessfully unfollowed {follow.user}"}, status=status.HTTP_204_NO_CONTENT)
        except Follow.DoesNotExist:
            return Response({'error': f"You have unfollowed User or the User is not found."}, status=status.HTTP_404_NOT_FOUND)
        
    def list_comments(self, request, book_id):
        # Retrieve the book owned by the authenticated user
        try:
            book_id = Book.objects.get(id=book_id)
            comments = Comment.objects.filter(book_id=book_id)
            serializer = CommentSerializer(comments, many=True, context={'request': request})
            return Response(serializer.data)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found or you are not the owner.'}, status=status.HTTP_404_NOT_FOUND)
    
    def update_comment(self, request, book_id, comment_id):
        try:
            comment = Comment.objects.get(id=comment_id, book_id=book_id, commenter=request.user)
            serializer = CommentSerializer(comment, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Comment.DoesNotExist:
            return Response({'error': 'Comment not found.'}, status=status.HTTP_404_NOT_FOUND)
        
    def delete_comment(self, request, book_id, comment_id):
        try:
            comment = Comment.objects.get(id=comment_id, book_id=book_id, commenter=request.user)
            comment.delete()
            return Response({"message": f"Comment with the id: {comment_id} has been deleted"}, status=status.HTTP_204_NO_CONTENT)
        except Comment.DoesNotExist:
            return Response({'error': 'Comment not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    def list_reviews(self, request, book_id):
        try:
            book = Book.objects.get(id=book_id)
            reviews = Review.objects.filter(book=book)
            serializer = ReviewSerializer(reviews, many=True, context={'request': request})
            return Response(serializer.data)
        except Book.DoesNotExist:
            return Response({'error': 'Book not found or you are not the owner.'}, status=status.HTTP_404_NOT_FOUND)

    def list_likes(self, request, book_id):
        try:
            book = Book.objects.get(id=book_id)
            likes = Like.objects.filter(book=book)
            serializer = LikeSerializer(likes, many=True, context={'request': request})
            if not serializer.data:
                return Response({'message': 'No likes found.'}, status=status.HTTP_404_NOT_FOUND)
            return Response(serializer.data)
        except Book.DoesNotExist:
            return Response({'error': 'could not return likes.'}, status=status.HTTP_404_NOT_FOUND)

    def delete_review(self, request, book_id, review_id):
        try:
            review = Review.objects.get(id=review_id, book_id=book_id, reviewer=request.user)
            review.delete()

            return Response({"Message": f"Review with the id: {review_id} has been deleted"}, status=status.HTTP_204_NO_CONTENT)
        except Review.DoesNotExist:
            return Response({'error': 'Review not found.'}, status=status.HTTP_404_NOT_FOUND)
        
    def delete_like(self, request, book_id, like_id):
        try:
            like = Like.objects.get(id=like_id, book_id=book_id, user=request.user)
            like.delete()
            return Response({"Message": f"Like with the id: {like_id} has been deleted"}, status=status.HTTP_204_NO_CONTENT)
        except Like.DoesNotExist:
            return Response({'error': 'Like not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    def retrieve_like(self, request, book_id, like_id):
        try:
            # Retrieve the book
            book = Book.objects.get(id=book_id)
        
            # Retrieve the like by its ID and associated book
            like = Like.objects.get(book=book_id, id=like_id)
            
            # Serialize the like
            serializer = LikeSerializer(like, context={'request': request})
        
            # Return the serialized like
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Like.DoesNotExist:
            return Response({'error': "Like not found for that book"}, status=status.HTTP_404_NOT_FOUND)



# Views for Cart and CartItem
class CartViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows cart to be viewed or edited.
    """
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]  # Only authenticated users can access

    def get_queryset(self):
        # Filter queryset to only include cart owned by the current user
        return Cart.objects.filter(user=self.request.user.profile)

    def perform_create(self, serializer):
        # Set the owner of the cart to the current user
        serializer.save(user=self.request.user.profile)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": f"Cart '{instance.id}' has been deleted."}, status=status.HTTP_204_NO_CONTENT)


class CartItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows cart items to be viewed or edited.
    """
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]  # Only authenticated users can access

    def get_queryset(self):
        # Filter queryset to only include cart items owned by the current user
        return CartItem.objects.filter(cart__user=self.request.user.profile)

    def perform_create(self, serializer):
        # Set the owner of the cart item to the current user
        serializer.save(cart__user=self.request.user.profile)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": f"Cart item '{instance.id}' has been deleted."}, status=status.HTTP_204_NO_CONTENT)
    
    def perform_destroy(self, instance):
        instance.delete()


# Views for Order and OrderItem
class OrderViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows orders to be viewed or edited.
    """
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]  # Only authenticated users can access

    def get_queryset(self):
        # Filter queryset to only include orders owned by the current user
        return Order.objects.filter(user=self.request.user.profile)

    def perform_create(self, serializer):
        # Set the owner of the order to the current user
        serializer.save(user=self.request.user.profile)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": f"Order '{instance.id}' has been deleted."}, status=status.HTTP_204_NO_CONTENT)


class OrderItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows order items to be viewed or edited.
    """
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]  # Only authenticated users can access

    def get_queryset(self):
        # Filter queryset to only include order items owned by the current user
        return OrderItem.objects.filter(order__user=self.request.user.profile)

    def perform_create(self, serializer):
        # Set the owner of the order item to the current user
        serializer.save(order__user=self.request.user.profile)
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({"message": f"Order item '{instance.id}' has been deleted."}, status=status.HTTP_204_NO_CONTENT)
    
    def perform_destroy(self, instance):
        instance.delete()