
import { generateClientToken } from '@vercel/blob';

export default async function handler(request, response) {
    try {
        const { pathname } = request.body; // Path where file will live in Blob storage

        const token = await generateClientToken({
            pathname,
            access: 'public',
            // No callbackUrl needed for now; we'll handle success in the frontend
        });

        return response.status(200).json(token);
    } catch (error) {
        return response.status(500).json({ error: error.message });
    }
}
