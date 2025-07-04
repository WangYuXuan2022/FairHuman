import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
import clip

class CLIPScore(nn.Module):
    def __init__(self, device='cuda'):
        super().__init__()
        self.device = device
        self.clip_model, self.preprocess = clip.load(name="/nvfile-heatstorage/zangxh/intern/wangyx/evaluation/HPSv2/improved-aesthetic-predictor-main/ViT-L-14.pt", device=self.device, jit=False, 
                                                   )
        
        if device == "cpu":
            self.clip_model.float()
        else:
            clip.model.convert_weights(self.clip_model) # Actually this line is unnecessary since clip by default already on float16

        # have clip.logit_scale require no grad.
        self.clip_model.logit_scale.requires_grad_(False)


    def score(self, prompt, image_path):
        
        if (type(image_path).__name__=='list'):
            _, rewards = self.inference_rank(prompt, image_path)
            return rewards
            
        # text encode
        text = clip.tokenize(prompt, truncate=True).to(self.device)
        txt_features = F.normalize(self.clip_model.encode_text(text))
        
        # image encode
        pil_image = Image.open(image_path)
        image = self.preprocess(pil_image).unsqueeze(0).to(self.device)
        image_features = F.normalize(self.clip_model.encode_image(image))
        
        # score
        rewards = torch.sum(torch.mul(txt_features, image_features), dim=1, keepdim=True)
        
        return rewards.detach().cpu().numpy().item()


    def inference_rank(self, prompt, generations_list):
        
        text = clip.tokenize(prompt, truncate=True).to(self.device)
        txt_feature = F.normalize(self.clip_model.encode_text(text))
        
        txt_set = []
        img_set = []
        for generations in generations_list:
            # image encode
            img_path = generations
            pil_image = Image.open(img_path)
            image = self.preprocess(pil_image).unsqueeze(0).to(self.device)
            image_features = F.normalize(self.clip_model.encode_image(image))
            img_set.append(image_features)
            txt_set.append(txt_feature)
            
        txt_features = torch.cat(txt_set, 0).float() # [image_num, feature_dim]
        img_features = torch.cat(img_set, 0).float() # [image_num, feature_dim]
        rewards = torch.sum(torch.mul(txt_features, img_features), dim=1, keepdim=True)
        rewards = torch.squeeze(rewards)
        _, rank = torch.sort(rewards, dim=0, descending=True)
        _, indices = torch.sort(rank, dim=0)
        indices = indices + 1
        
        return indices.detach().cpu().numpy().tolist(), rewards.detach().cpu().numpy().tolist()
    
if __name__ == '__main__':
    model = CLIPScore()
    prompt_list = open("/nvfile-heatstorage/zangxh/intern/wangyx/prompt_test.txt", "r").readlines()
    prompts = [prompt.strip() for prompt in prompt_list]
    clip_scores =[]
    for i, prompt in enumerate(prompts): 
            for img_path in os.listdir("/nvfile-heatstorage/zangxh/intern/wangyx/train_repo/1000_test/sdxl/gen/control_new/"+str(i)):
                    score = model.score(prompt,"/nvfile-heatstorage/zangxh/intern/wangyx/train_repo/1000_test/sdxl/gen/control_new/"+str(i)+"/"+img_path)
                    clip_scores.append(score)
    print( "Average clip score predicted by the model:")
    print( sum(clip_scores)/len(clip_scores) )
