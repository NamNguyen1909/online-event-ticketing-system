from sqlalchemy import TypeDecorator, String
import cloudinary
import cloudinary.uploader
from cloudinary import CloudinaryImage

class CloudinaryField(TypeDecorator):
    impl = String
    
    def __init__(self, folder=None, **kwargs):
        self.folder = folder or "uploads"
        super().__init__(length=255, **kwargs)
    
    def process_bind_param(self, value, dialect):
        # Khi lưu vào DB, chỉ lưu public_id
        if hasattr(value, 'public_id'):
            return value.public_id
        return value
    
    def process_result_value(self, value, dialect):
        # Khi đọc từ DB, trả về CloudinaryImage object
        if value:
            return CloudinaryImage(value)
        return None

class CloudinaryImageWrapper:
    def __init__(self, public_id=None):
        self.public_id = public_id
    
    def upload(self, file, **options):
        """Upload file to Cloudinary"""
        default_options = {
            'folder': 'uploads',
            'overwrite': True,
            'resource_type': 'image'
        }
        default_options.update(options)
        
        try:
            # Delete old image if exists
            if self.public_id:
                cloudinary.uploader.destroy(self.public_id)
            
            result = cloudinary.uploader.upload(file, **default_options)
            self.public_id = result['public_id']
            return result
        except Exception as e:
            print(f"Error uploading to Cloudinary: {e}")
            return None
    
    def delete(self):
        """Delete image from Cloudinary"""
        if self.public_id:
            try:
                return cloudinary.uploader.destroy(self.public_id)
            except Exception as e:
                print(f"Error deleting from Cloudinary: {e}")
                return None
    
    def url(self, **transformations):
        """Generate Cloudinary URL with transformations"""
        if self.public_id:
            return CloudinaryImage(self.public_id).build_url(**transformations)
        return None
    
    @property
    def image(self):
        """Get CloudinaryImage object"""
        if self.public_id:
            return CloudinaryImage(self.public_id)
        return None